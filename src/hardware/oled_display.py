#!/usr/bin/env python3
"""
Display OLED Manager per OriBruniRadioControls
Gestisce display OLED 0.96" I2C 128x64 sui lettori
"""

import os
import sys
import time
import threading
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import queue

# Import per display OLED
try:
    from luma.core.interface.serial import i2c
    from luma.core.render import canvas
    from luma.oled.device import ssd1306
    from PIL import Image, ImageDraw, ImageFont
    import qrcode
    OLED_AVAILABLE = True
except ImportError as e:
    print(f"OLED libraries not available: {e}")
    OLED_AVAILABLE = False

class DisplayMode(Enum):
    """Modi di visualizzazione del display"""
    STARTUP = "startup"
    STATUS = "status"
    PUNCH_INFO = "punch_info"
    TIME_SYNC = "time_sync"
    ERROR = "error"
    QR_CODE = "qr_code"
    MENU = "menu"

@dataclass
class PunchInfo:
    """Informazioni punzonatura per display"""
    card_number: str
    control: str
    punch_time: str
    timestamp: float

@dataclass
class StatusInfo:
    """Informazioni stato sistema"""
    device_name: str
    time_sync_status: bool
    last_punch_count: int
    mesh_connected: bool
    internet_connected: bool
    battery_level: Optional[int] = None
    temperature: Optional[float] = None

class OLEDDisplayManager:
    """Gestisce il display OLED per i lettori"""
    
    def __init__(self, device_name: str, i2c_address: int = 0x3C):
        self.device_name = device_name
        self.i2c_address = i2c_address
        
        # Setup logging
        self.logger = logging.getLogger(f'OLEDDisplay-{device_name}')
        
        # Display hardware
        self.device = None
        self.width = 128
        self.height = 64
        
        # Font paths
        self.fonts = self._load_fonts()
        
        # Display state
        self.current_mode = DisplayMode.STARTUP
        self.display_queue = queue.Queue(maxsize=50)
        self.last_update = 0
        self.update_interval = 0.1  # 100ms
        
        # Threading
        self._stop_event = threading.Event()
        self._display_thread = None
        self._lock = threading.RLock()
        
        # Data storage
        self.status_info = StatusInfo(
            device_name=device_name,
            time_sync_status=False,
            last_punch_count=0,
            mesh_connected=False,
            internet_connected=False
        )
        self.last_punch = None
        self.error_message = None
        
        # Menu system
        self.menu_items = [
            "Status Sistema",
            "Ultima Punzonatura", 
            "Sincronizzazione",
            "Connessioni",
            "QR Info",
            "Riavvia Display"
        ]
        self.menu_index = 0
        
        # Statistics
        self.stats = {
            'display_updates': 0,
            'errors': 0,
            'mode_changes': 0
        }
    
    def _load_fonts(self) -> Dict[str, Any]:
        """Carica font per il display"""
        fonts = {}
        
        # Font paths comuni su Raspberry Pi
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/TTF/DejaVuSans.ttf'
        ]
        
        try:
            # Trova font disponibili
            available_font = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    available_font = font_path
                    break
            
            if available_font:
                fonts['small'] = ImageFont.truetype(available_font, 10)
                fonts['medium'] = ImageFont.truetype(available_font, 12)
                fonts['large'] = ImageFont.truetype(available_font, 16)
                fonts['title'] = ImageFont.truetype(available_font, 14)
            else:
                # Fallback a font di default
                fonts['small'] = ImageFont.load_default()
                fonts['medium'] = ImageFont.load_default()
                fonts['large'] = ImageFont.load_default()
                fonts['title'] = ImageFont.load_default()
                
        except Exception as e:
            self.logger.warning(f"Errore caricamento font: {e}")
            # Usa font di default per tutto
            default_font = ImageFont.load_default()
            fonts = {
                'small': default_font,
                'medium': default_font,
                'large': default_font,
                'title': default_font
            }
        
        return fonts
    
    def initialize(self) -> bool:
        """Inizializza il display OLED"""
        if not OLED_AVAILABLE:
            self.logger.error("Librerie OLED non disponibili")
            return False
        
        try:
            # Crea interfaccia I2C
            serial = i2c(port=1, address=self.i2c_address)
            
            # Inizializza display SSD1306
            self.device = ssd1306(serial, width=self.width, height=self.height)
            
            # Test display
            with canvas(self.device) as draw:
                draw.text((0, 0), "OriBruni Init...", font=self.fonts['medium'], fill="white")
            
            self.logger.info(f"Display OLED inizializzato (I2C: 0x{self.i2c_address:02X})")
            return True
            
        except Exception as e:
            self.logger.error(f"Errore inizializzazione display: {e}")
            return False
    
    def start(self):
        """Avvia il manager del display"""
        if not self.initialize():
            return False
        
        if self._display_thread and self._display_thread.is_alive():
            return True
        
        self._stop_event.clear()
        self._display_thread = threading.Thread(
            target=self._display_loop,
            daemon=True,
            name=f'OLEDDisplay-{self.device_name}'
        )
        self._display_thread.start()
        
        # Mostra schermata di avvio
        self.show_startup()
        
        self.logger.info("Display manager avviato")
        return True
    
    def stop(self):
        """Ferma il manager del display"""
        self._stop_event.set()
        if self._display_thread:
            self._display_thread.join(timeout=5)
        
        # Pulisci display
        if self.device:
            try:
                self.device.clear()
            except:
                pass
        
        self.logger.info("Display manager fermato")
    
    def _display_loop(self):
        """Loop principale del display"""
        while not self._stop_event.is_set():
            try:
                # Processa messaggi in coda
                try:
                    message = self.display_queue.get_nowait()
                    self._process_display_message(message)
                except queue.Empty:
                    pass
                
                # Aggiorna display se necessario
                current_time = time.time()
                if current_time - self.last_update >= self.update_interval:
                    self._update_display()
                    self.last_update = current_time
                
                time.sleep(0.05)  # 50ms
                
            except Exception as e:
                self.logger.error(f"Errore nel loop display: {e}")
                self.stats['errors'] += 1
                time.sleep(1)
    
    def _process_display_message(self, message: Dict[str, Any]):
        """Processa un messaggio per il display"""
        msg_type = message.get('type')
        
        if msg_type == 'mode_change':
            self.set_mode(DisplayMode(message['mode']))
        elif msg_type == 'punch_info':
            self.show_punch_info(PunchInfo(**message['data']))
        elif msg_type == 'status_update':
            self.update_status(message['data'])
        elif msg_type == 'error':
            self.show_error(message['message'])
        elif msg_type == 'menu_navigate':
            self._navigate_menu(message['direction'])
    
    def _update_display(self):
        """Aggiorna il contenuto del display"""
        if not self.device:
            return
        
        try:
            with canvas(self.device) as draw:
                if self.current_mode == DisplayMode.STARTUP:
                    self._draw_startup(draw)
                elif self.current_mode == DisplayMode.STATUS:
                    self._draw_status(draw)
                elif self.current_mode == DisplayMode.PUNCH_INFO:
                    self._draw_punch_info(draw)
                elif self.current_mode == DisplayMode.TIME_SYNC:
                    self._draw_time_sync(draw)
                elif self.current_mode == DisplayMode.ERROR:
                    self._draw_error(draw)
                elif self.current_mode == DisplayMode.QR_CODE:
                    self._draw_qr_code(draw)
                elif self.current_mode == DisplayMode.MENU:
                    self._draw_menu(draw)
                else:
                    self._draw_default(draw)
            
            self.stats['display_updates'] += 1
            
        except Exception as e:
            self.logger.error(f"Errore aggiornamento display: {e}")
            self.stats['errors'] += 1
    
    def _draw_startup(self, draw):
        """Disegna schermata di avvio"""
        # Logo/Titolo
        draw.text((10, 5), "OriBruni", font=self.fonts['title'], fill="white")
        draw.text((10, 20), "RadioControls", font=self.fonts['medium'], fill="white")
        
        # Nome dispositivo
        draw.text((10, 35), f"Device: {self.device_name}", font=self.fonts['small'], fill="white")
        
        # Timestamp
        now = datetime.now().strftime("%H:%M:%S")
        draw.text((10, 50), f"Start: {now}", font=self.fonts['small'], fill="white")
    
    def _draw_status(self, draw):
        """Disegna schermata di stato"""
        y = 0
        
        # Header
        draw.text((0, y), f"{self.device_name}", font=self.fonts['title'], fill="white")
        y += 16
        
        # Ora corrente
        now = datetime.now().strftime("%H:%M:%S")
        draw.text((0, y), f"Time: {now}", font=self.fonts['small'], fill="white")
        y += 12
        
        # Stato connessioni
        mesh_icon = "●" if self.status_info.mesh_connected else "○"
        inet_icon = "●" if self.status_info.internet_connected else "○"
        sync_icon = "●" if self.status_info.time_sync_status else "○"
        
        draw.text((0, y), f"Mesh:{mesh_icon} Net:{inet_icon} Sync:{sync_icon}", 
                 font=self.fonts['small'], fill="white")
        y += 12
        
        # Contatore punzonature
        draw.text((0, y), f"Punches: {self.status_info.last_punch_count}", 
                 font=self.fonts['small'], fill="white")
        
        # Temperatura se disponibile
        if self.status_info.temperature:
            temp_text = f"{self.status_info.temperature:.1f}°C"
            draw.text((90, y), temp_text, font=self.fonts['small'], fill="white")
    
    def _draw_punch_info(self, draw):
        """Disegna informazioni ultima punzonatura"""
        if not self.last_punch:
            draw.text((10, 20), "Nessuna punzonatura", font=self.fonts['medium'], fill="white")
            return
        
        y = 0
        
        # Header
        draw.text((0, y), "ULTIMA PUNZONATURA", font=self.fonts['small'], fill="white")
        y += 14
        
        # Card number (grande)
        draw.text((0, y), f"Card: {self.last_punch.card_number}", 
                 font=self.fonts['large'], fill="white")
        y += 18
        
        # Control
        draw.text((0, y), f"Control: {self.last_punch.control}", 
                 font=self.fonts['medium'], fill="white")
        y += 14
        
        # Tempo
        draw.text((0, y), f"Time: {self.last_punch.punch_time}", 
                 font=self.fonts['small'], fill="white")
    
    def _draw_time_sync(self, draw):
        """Disegna informazioni sincronizzazione temporale"""
        y = 0
        
        draw.text((0, y), "TIME SYNC", font=self.fonts['title'], fill="white")
        y += 16
        
        status = "OK" if self.status_info.time_sync_status else "NO SYNC"
        draw.text((0, y), f"Status: {status}", font=self.fonts['medium'], fill="white")
        y += 14
        
        # Ora locale
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((0, y), now, font=self.fonts['small'], fill="white")
    
    def _draw_error(self, draw):
        """Disegna messaggio di errore"""
        y = 5
        
        draw.text((0, y), "ERRORE", font=self.fonts['title'], fill="white")
        y += 18
        
        if self.error_message:
            # Spezza il messaggio su più righe se necessario
            words = self.error_message.split()
            lines = []
            current_line = ""
            
            for word in words:
                test_line = current_line + " " + word if current_line else word
                # Stima larghezza (approssimativa)
                if len(test_line) * 6 < 128:  # 6 pixel per carattere circa
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            if current_line:
                lines.append(current_line)
            
            # Disegna le righe
            for line in lines[:3]:  # Max 3 righe
                draw.text((0, y), line, font=self.fonts['small'], fill="white")
                y += 12
    
    def _draw_qr_code(self, draw):
        """Disegna QR code con info dispositivo"""
        try:
            # Crea dati per QR code
            qr_data = {
                'device': self.device_name,
                'type': 'reader',
                'time': datetime.now().isoformat(),
                'punches': self.status_info.last_punch_count
            }
            
            # Genera QR code
            qr = qrcode.QRCode(version=1, box_size=2, border=1)
            qr.add_data(json.dumps(qr_data))
            qr.make(fit=True)
            
            # Converti in immagine
            qr_img = qr.make_image(fill_color="white", back_color="black")
            qr_img = qr_img.resize((60, 60))
            
            # Disegna QR code
            draw.bitmap((0, 0), qr_img, fill="white")
            
            # Info a lato
            draw.text((65, 0), self.device_name, font=self.fonts['small'], fill="white")
            draw.text((65, 12), f"Punches: {self.status_info.last_punch_count}", 
                     font=self.fonts['small'], fill="white")
            draw.text((65, 24), datetime.now().strftime("%H:%M"), 
                     font=self.fonts['small'], fill="white")
            
        except Exception as e:
            self.logger.error(f"Errore generazione QR code: {e}")
            draw.text((10, 20), "QR Error", font=self.fonts['medium'], fill="white")
    
    def _draw_menu(self, draw):
        """Disegna menu di navigazione"""
        y = 0
        
        draw.text((0, y), "MENU", font=self.fonts['title'], fill="white")
        y += 16
        
        # Mostra 3 elementi del menu
        start_idx = max(0, self.menu_index - 1)
        end_idx = min(len(self.menu_items), start_idx + 3)
        
        for i in range(start_idx, end_idx):
            item = self.menu_items[i]
            prefix = "> " if i == self.menu_index else "  "
            
            draw.text((0, y), f"{prefix}{item}", font=self.fonts['small'], fill="white")
            y += 12
    
    def _draw_default(self, draw):
        """Disegna schermata di default"""
        draw.text((10, 20), "OriBruni Display", font=self.fonts['medium'], fill="white")
        draw.text((10, 35), "Ready", font=self.fonts['small'], fill="white")
    
    # Metodi pubblici per controllo display
    
    def set_mode(self, mode: DisplayMode):
        """Cambia modalità display"""
        with self._lock:
            if self.current_mode != mode:
                self.current_mode = mode
                self.stats['mode_changes'] += 1
                self.logger.debug(f"Display mode changed to: {mode.value}")
    
    def show_startup(self):
        """Mostra schermata di avvio"""
        self.set_mode(DisplayMode.STARTUP)
        # Torna a status dopo 3 secondi
        threading.Timer(3.0, lambda: self.set_mode(DisplayMode.STATUS)).start()
    
    def show_punch_info(self, punch_info: PunchInfo):
        """Mostra informazioni punzonatura"""
        with self._lock:
            self.last_punch = punch_info
            self.set_mode(DisplayMode.PUNCH_INFO)
            # Torna a status dopo 5 secondi
            threading.Timer(5.0, lambda: self.set_mode(DisplayMode.STATUS)).start()
    
    def update_status(self, status_data: Dict[str, Any]):
        """Aggiorna informazioni di stato"""
        with self._lock:
            for key, value in status_data.items():
                if hasattr(self.status_info, key):
                    setattr(self.status_info, key, value)
    
    def show_error(self, message: str):
        """Mostra messaggio di errore"""
        with self._lock:
            self.error_message = message
            self.set_mode(DisplayMode.ERROR)
            # Torna a status dopo 10 secondi
            threading.Timer(10.0, lambda: self.set_mode(DisplayMode.STATUS)).start()
    
    def show_qr_code(self):
        """Mostra QR code"""
        self.set_mode(DisplayMode.QR_CODE)
    
    def show_menu(self):
        """Mostra menu"""
        self.set_mode(DisplayMode.MENU)
    
    def _navigate_menu(self, direction: str):
        """Naviga nel menu"""
        with self._lock:
            if direction == "up":
                self.menu_index = max(0, self.menu_index - 1)
            elif direction == "down":
                self.menu_index = min(len(self.menu_items) - 1, self.menu_index + 1)
            elif direction == "select":
                self._execute_menu_item()
    
    def _execute_menu_item(self):
        """Esegue elemento menu selezionato"""
        item = self.menu_items[self.menu_index]
        
        if item == "Status Sistema":
            self.set_mode(DisplayMode.STATUS)
        elif item == "Ultima Punzonatura":
            self.set_mode(DisplayMode.PUNCH_INFO)
        elif item == "Sincronizzazione":
            self.set_mode(DisplayMode.TIME_SYNC)
        elif item == "QR Info":
            self.set_mode(DisplayMode.QR_CODE)
        elif item == "Riavvia Display":
            self.restart_display()
    
    def restart_display(self):
        """Riavvia il display"""
        self.logger.info("Riavvio display...")
        self.stop()
        time.sleep(1)
        self.start()
    
    def get_stats(self) -> Dict[str, Any]:
        """Restituisce statistiche display"""
        return {
            'current_mode': self.current_mode.value,
            'stats': self.stats.copy(),
            'device_available': self.device is not None,
            'last_update': self.last_update
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Health check del display"""
        health = {
            'status': 'healthy',
            'issues': []
        }
        
        if not OLED_AVAILABLE:
            health['status'] = 'error'
            health['issues'].append('OLED libraries not available')
        
        if not self.device:
            health['status'] = 'error'
            health['issues'].append('Display device not initialized')
        
        if self.stats['errors'] > 10:
            health['status'] = 'warning'
            health['issues'].append('High error count')
        
        return health


# Integrazione con sistema esistente
class DisplayIntegration:
    """Integrazione display con sistema OriBruni"""
    
    @staticmethod
    def create_display_from_config(config_path: str) -> Optional[OLEDDisplayManager]:
        """Crea display manager da configurazione"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            device_name = config['device']['name']
            display_config = config.get('display', {})
            
            i2c_address = int(display_config.get('i2c_address', '0x3C'), 16)
            
            display = OLEDDisplayManager(device_name, i2c_address)
            return display
            
        except Exception as e:
            logging.error(f"Errore creazione display da config: {e}")
            return None
    
    @staticmethod
    def integrate_with_sportident(display_manager, sportident_reader):
        """Integra display con lettore SportIdent"""
        def on_punch_received(card_number, control, punch_time):
            punch_info = PunchInfo(
                card_number=str(card_number),
                control=str(control),
                punch_time=punch_time,
                timestamp=time.time()
            )
            display_manager.show_punch_info(punch_info)
            
            # Aggiorna contatore
            display_manager.update_status({
                'last_punch_count': display_manager.status_info.last_punch_count + 1
            })
        
        # Collega callback se disponibile
        if hasattr(sportident_reader, 'on_punch_callback'):
            sportident_reader.on_punch_callback = on_punch_received
    
    @staticmethod
    def integrate_with_time_sync(display_manager, time_sync_manager):
        """Integra display con time sync manager"""
        def on_time_updated(drift, new_time):
            display_manager.update_status({
                'time_sync_status': True
            })
            # Mostra brevemente info sync se drift significativo
            if abs(drift) > 5.0:
                display_manager.show_error(f"Time updated: {drift:.1f}s drift")
        
        if hasattr(time_sync_manager, 'on_time_updated'):
            time_sync_manager.on_time_updated = on_time_updated
    
    @staticmethod
    def integrate_with_meshtastic(display_manager, meshtastic_service):
        """Integra display con servizio Meshtastic"""
        def on_mesh_status_change(connected):
            display_manager.update_status({
                'mesh_connected': connected
            })
        
        def on_internet_status_change(connected):
            display_manager.update_status({
                'internet_connected': connected
            })
        
        # Collega callbacks se disponibili
        if hasattr(meshtastic_service, 'on_mesh_status_change'):
            meshtastic_service.on_mesh_status_change = on_mesh_status_change
        
        if hasattr(meshtastic_service, 'on_internet_status_change'):
            meshtastic_service.on_internet_status_change = on_internet_status_change


def main():
    """Test del display OLED"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Display OLED OriBruni')
    parser.add_argument('--device-name', default='test-reader', help='Nome dispositivo')
    parser.add_argument('--i2c-address', default='0x3C', help='Indirizzo I2C display')
    parser.add_argument('--demo', action='store_true', help='Modalità demo')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Crea display manager
    i2c_addr = int(args.i2c_address, 16)
    display = OLEDDisplayManager(args.device_name, i2c_addr)
    
    if not display.start():
        print("Errore avvio display")
        sys.exit(1)
    
    try:
        if args.demo:
            print("Modalità demo - premi Ctrl+C per uscire")
            
            # Demo sequence
            time.sleep(3)  # Startup screen
            
            # Aggiorna status
            display.update_status({
                'mesh_connected': True,
                'internet_connected': False,
                'time_sync_status': True,
                'last_punch_count': 42,
                'temperature': 23.5
            })
            
            time.sleep(5)
            
            # Simula punzonatura
            punch = PunchInfo(
                card_number="123456",
                control="31",
                punch_time="14:32:15",
                timestamp=time.time()
            )
            display.show_punch_info(punch)
            
            time.sleep(5)
            
            # Mostra QR code
            display.show_qr_code()
            
            time.sleep(5)
            
            # Mostra errore
            display.show_error("Test error message for display")
            
            time.sleep(5)
            
            # Torna a status
            display.set_mode(DisplayMode.STATUS)
            
            # Mantieni attivo
            while True:
                time.sleep(1)
        else:
            print("Display avviato - premi Ctrl+C per uscire")
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\nChiusura display...")
    finally:
        display.stop()
        print("Display fermato")


if __name__ == '__main__':
    main()

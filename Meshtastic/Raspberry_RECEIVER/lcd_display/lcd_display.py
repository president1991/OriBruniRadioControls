#!/usr/bin/env python3
"""
Script per controllare un display LCD 20x4 con interfaccia I2C
Mostra l'IP privato del Raspberry Pi sul display
"""

import time
import socket
import netifaces
from RPLCD.i2c import CharLCD
import logging

# Configurazione logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class LCDController:
    def __init__(self, i2c_address=0x27, i2c_port=1):
        """
        Inizializza il controller LCD
        
        Args:
            i2c_address: Indirizzo I2C del display (default 0x27)
            i2c_port: Porta I2C (default 1 per Raspberry Pi)
        """
        self.i2c_address = i2c_address
        self.i2c_port = i2c_port
        self.lcd = None
        self.initialize_lcd()
    
    def initialize_lcd(self):
        """Inizializza la connessione al display LCD"""
        try:
            self.lcd = CharLCD(
                i2c_expander='PCF8574',
                address=self.i2c_address,
                port=self.i2c_port,
                cols=20,
                rows=4,
                dotsize=8,
                charmap='A02',
                auto_linebreaks=True
            )
            logger.info(f"LCD inizializzato correttamente su indirizzo I2C {hex(self.i2c_address)}")
            
            # Test iniziale
            self.lcd.clear()
            self.lcd.write_string("LCD Inizializzato")
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Errore nell'inizializzazione del LCD: {e}")
            raise
    
    def get_private_ip(self):
        """
        Ottiene l'IP privato del Raspberry Pi
        
        Returns:
            str: IP privato o messaggio di errore
        """
        try:
            # Metodo 1: Prova a connettersi a un server esterno per determinare l'IP locale
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                return local_ip
        except:
            pass
        
        try:
            # Metodo 2: Usa netifaces per ottenere gli indirizzi delle interfacce
            interfaces = netifaces.interfaces()
            for interface in interfaces:
                if interface.startswith('eth') or interface.startswith('wlan'):
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            ip = addr['addr']
                            if not ip.startswith('127.'):
                                return ip
        except:
            pass
        
        return "IP non trovato"
    
    def get_hostname(self):
        """
        Ottiene il nome host del sistema
        
        Returns:
            str: Nome host
        """
        try:
            return socket.gethostname()
        except:
            return "hostname sconosciuto"
    
    def display_ip_info(self):
        """Mostra le informazioni IP sul display LCD"""
        try:
            ip_address = self.get_private_ip()
            hostname = self.get_hostname()
            current_time = time.strftime("%H:%M:%S")
            current_date = time.strftime("%d/%m/%Y")
            
            # Pulisce il display
            self.lcd.clear()
            
            # Riga 1: Titolo
            self.lcd.cursor_pos = (0, 0)
            self.lcd.write_string("OriBruni Receiver")
            
            # Riga 2: IP
            self.lcd.cursor_pos = (1, 0)
            self.lcd.write_string(f"IP: {ip_address}")
            
            # Riga 3: Hostname
            self.lcd.cursor_pos = (2, 0)
            hostname_display = hostname[:20]  # Tronca se troppo lungo
            self.lcd.write_string(f"Host: {hostname_display}")
            
            # Riga 4: Data e ora
            self.lcd.cursor_pos = (3, 0)
            self.lcd.write_string(f"{current_date} {current_time}")
            
            logger.info(f"Informazioni aggiornate sul display - IP: {ip_address}")
            
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento del display: {e}")
            try:
                self.lcd.clear()
                self.lcd.write_string("Errore display")
            except:
                pass
    
    def display_custom_message(self, lines):
        """
        Mostra un messaggio personalizzato sul display
        
        Args:
            lines: Lista di stringhe (max 4 righe, max 20 caratteri per riga)
        """
        try:
            self.lcd.clear()
            for i, line in enumerate(lines[:4]):  # Max 4 righe
                self.lcd.cursor_pos = (i, 0)
                self.lcd.write_string(line[:20])  # Max 20 caratteri per riga
        except Exception as e:
            logger.error(f"Errore nella visualizzazione del messaggio personalizzato: {e}")
    
    def clear_display(self):
        """Pulisce il display"""
        try:
            self.lcd.clear()
        except Exception as e:
            logger.error(f"Errore nella pulizia del display: {e}")
    
    def close(self):
        """Chiude la connessione al display"""
        try:
            if self.lcd:
                self.lcd.clear()
                self.lcd.close()
            logger.info("Connessione LCD chiusa")
        except Exception as e:
            logger.error(f"Errore nella chiusura del LCD: {e}")

def main():
    """Funzione principale"""
    lcd_controller = None
    
    try:
        # Inizializza il controller LCD
        logger.info("Inizializzazione del controller LCD...")
        lcd_controller = LCDController()
        
        # Mostra le informazioni IP
        logger.info("Visualizzazione informazioni IP...")
        lcd_controller.display_ip_info()
        
        # Mantiene il display attivo e aggiorna ogni 30 secondi
        logger.info("Display attivo. Aggiornamento ogni 30 secondi. Premi Ctrl+C per uscire.")
        
        while True:
            time.sleep(30)  # Aggiorna ogni 30 secondi
            lcd_controller.display_ip_info()
            
    except KeyboardInterrupt:
        logger.info("Interruzione da tastiera ricevuta")
    except Exception as e:
        logger.error(f"Errore generale: {e}")
    finally:
        if lcd_controller:
            lcd_controller.close()
        logger.info("Programma terminato")

if __name__ == "__main__":
    main()

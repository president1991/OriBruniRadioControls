#!/usr/bin/env python3
"""
Time Sync Manager per OriBruniRadioControls
Gestisce la sincronizzazione temporale tra RICEVITORI e LETTORI via Meshtastic
"""

import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import IntEnum
import json

class MessageType(IntEnum):
    """Tipi di messaggio per il sistema"""
    TELEMETRY = 0
    PUNCHES = 1
    TIME_SYNC = 2  # Nuovo tipo per sincronizzazione temporale

@dataclass
class TimeSyncMessage:
    """Messaggio di sincronizzazione temporale"""
    timestamp: float
    sender_name: str
    sender_type: str  # 'receiver' o 'reader'
    sequence_number: int
    timezone_offset: int = 0  # Offset timezone in secondi

@dataclass
class TimeStatus:
    """Stato della sincronizzazione temporale"""
    last_sync: Optional[float] = None
    time_drift: float = 0.0  # Differenza in secondi
    sync_count: int = 0
    sync_source: Optional[str] = None
    is_synced: bool = False

class TimeSyncManager:
    """Gestisce la sincronizzazione temporale nel sistema mesh"""
    
    def __init__(self, device_name: str, device_type: str, 
                 sync_interval: int = 300, max_drift: float = 15.0):
        """
        Args:
            device_name: Nome del dispositivo
            device_type: 'receiver' o 'reader'
            sync_interval: Intervallo invio sync in secondi (solo per receiver)
            max_drift: Massima differenza temporale accettabile in secondi
        """
        self.device_name = device_name
        self.device_type = device_type.lower()
        self.sync_interval = sync_interval
        self.max_drift = max_drift
        
        # Stato interno
        self.time_status = TimeStatus()
        self.sequence_number = 0
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._sync_thread = None
        
        # Callbacks
        self.on_time_updated: Optional[Callable[[float, float], None]] = None
        self.send_message_callback: Optional[Callable[[str], bool]] = None
        
        # Logger
        self.logger = logging.getLogger(f'TimeSyncManager-{device_name}')
        
        # Statistiche
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'time_updates': 0,
            'sync_errors': 0
        }
    
    def start(self):
        """Avvia il manager di sincronizzazione"""
        if self._sync_thread and self._sync_thread.is_alive():
            return
        
        self._stop_event.clear()
        
        # Solo i receiver inviano periodicamente messaggi di sync
        if self.device_type == 'receiver':
            self._sync_thread = threading.Thread(
                target=self._sync_loop, 
                daemon=True,
                name=f'TimeSync-{self.device_name}'
            )
            self._sync_thread.start()
            self.logger.info(f"Time sync manager avviato (receiver mode, interval: {self.sync_interval}s)")
        else:
            self.logger.info("Time sync manager avviato (reader mode, solo ricezione)")
    
    def stop(self):
        """Ferma il manager di sincronizzazione"""
        self._stop_event.set()
        if self._sync_thread:
            self._sync_thread.join(timeout=5)
        self.logger.info("Time sync manager fermato")
    
    def _sync_loop(self):
        """Loop principale per invio messaggi di sync (solo receiver)"""
        while not self._stop_event.wait(self.sync_interval):
            try:
                self.send_time_sync()
            except Exception as e:
                self.logger.error(f"Errore invio time sync: {e}")
                self.stats['sync_errors'] += 1
    
    def send_time_sync(self) -> bool:
        """Invia un messaggio di sincronizzazione temporale"""
        if not self.send_message_callback:
            self.logger.warning("Callback invio messaggio non configurato")
            return False
        
        with self._lock:
            self.sequence_number += 1
            
            sync_message = TimeSyncMessage(
                timestamp=time.time(),
                sender_name=self.device_name,
                sender_type=self.device_type,
                sequence_number=self.sequence_number,
                timezone_offset=int(time.timezone)
            )
            
            # Formato messaggio: tipo;timestamp;nome;tipo_dispositivo;sequence;timezone
            payload_parts = [
                str(MessageType.TIME_SYNC.value),
                str(sync_message.timestamp),
                sync_message.sender_name,
                sync_message.sender_type,
                str(sync_message.sequence_number),
                str(sync_message.timezone_offset)
            ]
            
            payload = ";".join(payload_parts)
            
            try:
                success = self.send_message_callback(payload)
                if success:
                    self.stats['messages_sent'] += 1
                    self.logger.debug(f"Time sync inviato: seq={self.sequence_number}")
                return success
            except Exception as e:
                self.logger.error(f"Errore invio time sync: {e}")
                self.stats['sync_errors'] += 1
                return False
    
    def process_time_sync_message(self, payload: str) -> bool:
        """Processa un messaggio di sincronizzazione ricevuto"""
        try:
            parts = payload.split(';')
            if len(parts) < 6:
                self.logger.warning(f"Messaggio time sync malformato: {payload}")
                return False
            
            msg_type = int(parts[0])
            if msg_type != MessageType.TIME_SYNC.value:
                return False  # Non è un messaggio di time sync
            
            sync_message = TimeSyncMessage(
                timestamp=float(parts[1]),
                sender_name=parts[2],
                sender_type=parts[3],
                sequence_number=int(parts[4]),
                timezone_offset=int(parts[5]) if len(parts) > 5 else 0
            )
            
            # Non processare i propri messaggi
            if sync_message.sender_name == self.device_name:
                return True
            
            self.stats['messages_received'] += 1
            
            # Calcola drift temporale
            current_time = time.time()
            time_drift = sync_message.timestamp - current_time
            
            self.logger.debug(
                f"Time sync ricevuto da {sync_message.sender_name}: "
                f"drift={time_drift:.2f}s, seq={sync_message.sequence_number}"
            )
            
            # Aggiorna stato
            with self._lock:
                self.time_status.last_sync = current_time
                self.time_status.time_drift = time_drift
                self.time_status.sync_count += 1
                self.time_status.sync_source = sync_message.sender_name
                
                # Determina se è necessario aggiornare l'orologio
                needs_update = abs(time_drift) > self.max_drift
                
                if needs_update:
                    self.logger.warning(
                        f"Drift temporale elevato: {time_drift:.2f}s da {sync_message.sender_name}"
                    )
                    
                    # Solo i reader aggiornano il proprio orologio
                    if self.device_type == 'reader':
                        success = self._update_system_time(sync_message.timestamp)
                        if success:
                            self.time_status.is_synced = True
                            self.stats['time_updates'] += 1
                            
                            # Callback per notificare l'aggiornamento
                            if self.on_time_updated:
                                self.on_time_updated(time_drift, sync_message.timestamp)
                        else:
                            self.time_status.is_synced = False
                    else:
                        # I receiver non aggiornano il proprio orologio
                        self.time_status.is_synced = True
                else:
                    self.time_status.is_synced = True
                    self.logger.debug(f"Orologio sincronizzato (drift: {time_drift:.2f}s)")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Errore processamento time sync: {e}")
            self.stats['sync_errors'] += 1
            return False
    
    def _update_system_time(self, new_timestamp: float) -> bool:
        """Aggiorna l'orologio di sistema (solo su Linux/Raspberry Pi)"""
        try:
            import subprocess
            import os
            
            # Converti timestamp in formato date
            new_datetime = datetime.fromtimestamp(new_timestamp)
            date_string = new_datetime.strftime('%Y-%m-%d %H:%M:%S')
            
            # Su Raspberry Pi, usa sudo date per aggiornare l'orologio
            if os.path.exists('/usr/bin/sudo') and os.path.exists('/bin/date'):
                cmd = ['sudo', 'date', '-s', date_string]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    self.logger.info(f"Orologio di sistema aggiornato: {date_string}")
                    return True
                else:
                    self.logger.error(f"Errore aggiornamento orologio: {result.stderr}")
                    return False
            else:
                self.logger.warning("Comando date non disponibile, aggiornamento orologio saltato")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout aggiornamento orologio di sistema")
            return False
        except Exception as e:
            self.logger.error(f"Errore aggiornamento orologio di sistema: {e}")
            return False
    
    def get_time_status(self) -> Dict[str, Any]:
        """Restituisce lo stato della sincronizzazione temporale"""
        with self._lock:
            status = {
                'device_name': self.device_name,
                'device_type': self.device_type,
                'is_synced': self.time_status.is_synced,
                'last_sync': self.time_status.last_sync,
                'time_drift': self.time_status.time_drift,
                'sync_count': self.time_status.sync_count,
                'sync_source': self.time_status.sync_source,
                'max_drift': self.max_drift,
                'stats': self.stats.copy(),
                'current_time': time.time()
            }
            
            # Aggiungi informazioni sulla sincronizzazione
            if self.time_status.last_sync:
                time_since_sync = time.time() - self.time_status.last_sync
                status['time_since_last_sync'] = time_since_sync
                status['sync_age_warning'] = time_since_sync > (self.sync_interval * 2)
            
            return status
    
    def force_sync_request(self) -> bool:
        """Forza una richiesta di sincronizzazione (per reader)"""
        if self.device_type != 'reader':
            self.logger.warning("Force sync disponibile solo per reader")
            return False
        
        # Invia un messaggio speciale di richiesta sync
        # I receiver dovrebbero rispondere con un time sync
        return self.send_time_sync()
    
    def health_check(self) -> Dict[str, Any]:
        """Esegue un health check del time sync manager"""
        status = self.get_time_status()
        
        health = {
            'status': 'healthy',
            'issues': [],
            'details': status
        }
        
        # Controlla problemi
        if not status['is_synced']:
            health['status'] = 'warning'
            health['issues'].append('Orologio non sincronizzato')
        
        if status.get('time_since_last_sync', 0) > (self.sync_interval * 3):
            health['status'] = 'warning'
            health['issues'].append('Nessuna sincronizzazione recente')
        
        if abs(status['time_drift']) > self.max_drift:
            health['status'] = 'error'
            health['issues'].append(f"Drift temporale eccessivo: {status['time_drift']:.2f}s")
        
        if status['stats']['sync_errors'] > status['stats']['messages_received'] * 0.1:
            health['status'] = 'warning'
            health['issues'].append('Troppi errori di sincronizzazione')
        
        return health


# Utility per integrazione con il sistema esistente
class TimeSyncIntegration:
    """Integrazione del time sync con il sistema Meshtastic esistente"""
    
    @staticmethod
    def integrate_with_meshtastic_service(meshtastic_service, time_sync_manager):
        """Integra il time sync manager con il servizio Meshtastic"""
        
        # Configura callback per invio messaggi
        def send_via_meshtastic(payload: str) -> bool:
            try:
                if hasattr(meshtastic_service, 'mesh') and meshtastic_service.mesh:
                    meshtastic_service.mesh.sendText(payload)
                    return True
                return False
            except Exception as e:
                logging.error(f"Errore invio time sync via Meshtastic: {e}")
                return False
        
        time_sync_manager.send_message_callback = send_via_meshtastic
        
        # Modifica il callback di ricezione per processare time sync
        original_on_receive = meshtastic_service.on_receive if hasattr(meshtastic_service, 'on_receive') else None
        
        def enhanced_on_receive(pkt, interface):
            # Processa normalmente il pacchetto
            if original_on_receive:
                original_on_receive(pkt, interface)
            
            # Estrai payload per time sync
            raw = pkt.get('decoded', pkt)
            text = raw.get('payload') or raw.get('text') or str(pkt)
            
            # Prova a processare come time sync
            if isinstance(text, str) and text.startswith('2;'):  # MessageType.TIME_SYNC
                time_sync_manager.process_time_sync_message(text)
        
        # Sostituisci il callback
        if hasattr(meshtastic_service, 'mesh') and meshtastic_service.mesh:
            meshtastic_service.mesh.onReceive(enhanced_on_receive)
    
    @staticmethod
    def create_time_sync_endpoint(app, time_sync_manager):
        """Aggiunge endpoint API per time sync a FastAPI app"""
        
        @app.get("/api/time_sync/status")
        def get_time_sync_status():
            """Restituisce lo stato della sincronizzazione temporale"""
            return time_sync_manager.get_time_status()
        
        @app.get("/api/time_sync/health")
        def get_time_sync_health():
            """Health check della sincronizzazione temporale"""
            return time_sync_manager.health_check()
        
        @app.post("/api/time_sync/force")
        def force_time_sync():
            """Forza una sincronizzazione temporale"""
            success = time_sync_manager.force_sync_request()
            return {"success": success}


if __name__ == '__main__':
    # Test del time sync manager
    logging.basicConfig(level=logging.INFO)
    
    # Test come receiver
    print("Test TimeSyncManager come RECEIVER:")
    receiver_sync = TimeSyncManager("receiver-01", "receiver", sync_interval=10)
    
    # Mock callback per invio
    def mock_send(payload):
        print(f"SEND: {payload}")
        return True
    
    receiver_sync.send_message_callback = mock_send
    receiver_sync.start()
    
    # Invia un messaggio di sync
    receiver_sync.send_time_sync()
    
    # Test come reader
    print("\nTest TimeSyncManager come READER:")
    reader_sync = TimeSyncManager("reader-01", "reader", max_drift=15.0)
    
    # Callback per notifica aggiornamento tempo
    def on_time_updated(drift, new_time):
        print(f"Orologio aggiornato: drift={drift:.2f}s, nuovo_tempo={new_time}")
    
    reader_sync.on_time_updated = on_time_updated
    reader_sync.start()
    
    # Simula ricezione messaggio di sync
    test_payload = f"2;{time.time()};receiver-01;receiver;1;0"
    reader_sync.process_time_sync_message(test_payload)
    
    # Mostra stato
    print(f"\nStato receiver: {receiver_sync.get_time_status()}")
    print(f"Stato reader: {reader_sync.get_time_status()}")
    
    # Health check
    print(f"\nHealth receiver: {receiver_sync.health_check()}")
    print(f"Health reader: {reader_sync.health_check()}")
    
    # Cleanup
    receiver_sync.stop()
    reader_sync.stop()
    
    print("\nTest completato!")

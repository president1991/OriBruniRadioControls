#!/usr/bin/env python3
"""
Thread-Safe Buffer per OriBruniRadioControls
Gestisce buffer condivisi tra thread in modo sicuro per la lettura seriale
"""

import threading
import time
import logging
from typing import Optional, Tuple, List
from collections import deque
from dataclasses import dataclass

@dataclass
class FrameInfo:
    """Informazioni su un frame estratto"""
    frame: bytes
    timestamp: float
    buffer_size_before: int
    buffer_size_after: int

class ThreadSafeBuffer:
    """Buffer thread-safe per dati seriali con estrazione frame SportIdent"""
    
    def __init__(self, max_size: int = 8192, stats_enabled: bool = True):
        self._buffer = bytearray()
        self._lock = threading.RLock()  # Reentrant lock per nested calls
        self._max_size = max_size
        self._stats_enabled = stats_enabled
        
        # Statistiche
        self._stats = {
            'bytes_received': 0,
            'frames_extracted': 0,
            'buffer_overflows': 0,
            'extraction_errors': 0,
            'last_activity': 0
        }
        
        # Logger
        self.logger = logging.getLogger('ThreadSafeBuffer')
    
    def extend(self, data: bytes) -> bool:
        """Aggiunge dati al buffer in modo thread-safe"""
        if not data:
            return True
            
        with self._lock:
            # Controlla overflow
            if len(self._buffer) + len(data) > self._max_size:
                # Rimuovi dati vecchi per fare spazio
                overflow_size = len(self._buffer) + len(data) - self._max_size
                self._buffer = self._buffer[overflow_size:]
                
                if self._stats_enabled:
                    self._stats['buffer_overflows'] += 1
                    
                self.logger.warning(f"Buffer overflow: rimossi {overflow_size} bytes")
            
            self._buffer.extend(data)
            
            if self._stats_enabled:
                self._stats['bytes_received'] += len(data)
                self._stats['last_activity'] = time.time()
            
            return True
    
    def extract_frame(self) -> Optional[FrameInfo]:
        """Estrae un frame SportIdent dal buffer in modo thread-safe"""
        with self._lock:
            try:
                buffer_size_before = len(self._buffer)
                
                # Rimuovi eventuali byte di wakeup (0xFF) all'inizio
                while self._buffer and self._buffer[0] == 0xFF:
                    self._buffer.pop(0)
                
                if not self._buffer:
                    return None
                
                # Cerca STX (0x02)
                try:
                    start_idx = self._buffer.index(0x02)
                except ValueError:
                    return None
                
                # Rimuovi dati prima di STX se presenti
                if start_idx > 0:
                    self._buffer = self._buffer[start_idx:]
                
                # Verifica se abbiamo abbastanza dati per leggere la lunghezza
                if len(self._buffer) < 3:
                    return None
                
                # Leggi lunghezza frame (terzo byte dopo STX)
                frame_length = self._buffer[2]
                total_length = frame_length + 6  # lunghezza + STX + CMD + LEN + CRC1 + CRC2 + ETX
                
                # Verifica se abbiamo il frame completo
                if len(self._buffer) < total_length:
                    return None
                
                # Estrai il frame
                frame = bytes(self._buffer[:total_length])
                self._buffer = self._buffer[total_length:]
                
                # Verifica ETX (0x03)
                if frame[-1] != 0x03:
                    self.logger.error(f"Frame senza ETX valido: {frame.hex()}")
                    if self._stats_enabled:
                        self._stats['extraction_errors'] += 1
                    return None
                
                buffer_size_after = len(self._buffer)
                
                if self._stats_enabled:
                    self._stats['frames_extracted'] += 1
                
                return FrameInfo(
                    frame=frame,
                    timestamp=time.time(),
                    buffer_size_before=buffer_size_before,
                    buffer_size_after=buffer_size_after
                )
                
            except Exception as e:
                self.logger.error(f"Errore estrazione frame: {e}")
                if self._stats_enabled:
                    self._stats['extraction_errors'] += 1
                return None
    
    def extract_all_frames(self) -> List[FrameInfo]:
        """Estrae tutti i frame disponibili dal buffer"""
        frames = []
        while True:
            frame_info = self.extract_frame()
            if frame_info is None:
                break
            frames.append(frame_info)
        return frames
    
    def peek(self, size: int = None) -> bytes:
        """Legge dati dal buffer senza rimuoverli"""
        with self._lock:
            if size is None:
                return bytes(self._buffer)
            return bytes(self._buffer[:size])
    
    def clear(self) -> int:
        """Svuota il buffer e restituisce il numero di byte rimossi"""
        with self._lock:
            size = len(self._buffer)
            self._buffer.clear()
            return size
    
    def size(self) -> int:
        """Restituisce la dimensione attuale del buffer"""
        with self._lock:
            return len(self._buffer)
    
    def is_empty(self) -> bool:
        """Verifica se il buffer è vuoto"""
        with self._lock:
            return len(self._buffer) == 0
    
    def get_stats(self) -> dict:
        """Restituisce statistiche del buffer"""
        with self._lock:
            stats = self._stats.copy()
            stats['current_buffer_size'] = len(self._buffer)
            stats['max_buffer_size'] = self._max_size
            stats['buffer_utilization'] = len(self._buffer) / self._max_size * 100
            return stats
    
    def reset_stats(self):
        """Resetta le statistiche"""
        with self._lock:
            self._stats = {
                'bytes_received': 0,
                'frames_extracted': 0,
                'buffer_overflows': 0,
                'extraction_errors': 0,
                'last_activity': time.time()
            }
    
    def health_check(self) -> dict:
        """Esegue un health check del buffer"""
        with self._lock:
            stats = self.get_stats()
            
            health = {
                'status': 'healthy',
                'issues': [],
                'stats': stats
            }
            
            # Controlla problemi
            if stats['buffer_utilization'] > 90:
                health['status'] = 'warning'
                health['issues'].append('Buffer quasi pieno')
            
            if stats['buffer_overflows'] > 0:
                health['status'] = 'warning'
                health['issues'].append(f"Buffer overflow: {stats['buffer_overflows']} volte")
            
            if stats['extraction_errors'] > stats['frames_extracted'] * 0.1:
                health['status'] = 'error'
                health['issues'].append('Troppi errori di estrazione frame')
            
            # Controlla attività recente
            if time.time() - stats['last_activity'] > 300:  # 5 minuti
                health['status'] = 'warning'
                health['issues'].append('Nessuna attività recente')
            
            return health


class MessageQueue:
    """Coda thread-safe per messaggi con priorità"""
    
    def __init__(self, max_size: int = 1000):
        self._queue = deque()
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._max_size = max_size
        self._closed = False
        
        # Statistiche
        self._stats = {
            'messages_added': 0,
            'messages_processed': 0,
            'queue_overflows': 0,
            'max_queue_size': 0
        }
        
        self.logger = logging.getLogger('MessageQueue')
    
    def put(self, message: any, priority: int = 0, timeout: float = None) -> bool:
        """Aggiunge un messaggio alla coda con priorità"""
        with self._condition:
            if self._closed:
                return False
            
            # Controlla overflow
            if len(self._queue) >= self._max_size:
                # Rimuovi messaggio più vecchio con priorità più bassa
                if self._queue:
                    # Trova il messaggio con priorità più bassa
                    min_priority_idx = 0
                    min_priority = self._queue[0][1]  # (message, priority, timestamp)
                    
                    for i, (_, prio, _) in enumerate(self._queue):
                        if prio < min_priority:
                            min_priority = prio
                            min_priority_idx = i
                    
                    # Rimuovi solo se la nuova priorità è maggiore
                    if priority > min_priority:
                        removed = self._queue[min_priority_idx]
                        del self._queue[min_priority_idx]
                        self.logger.warning(f"Rimosso messaggio priorità {removed[1]} per fare spazio")
                        self._stats['queue_overflows'] += 1
                    else:
                        self.logger.warning("Coda piena, messaggio scartato")
                        return False
            
            # Inserisci messaggio ordinato per priorità (priorità più alta prima)
            timestamp = time.time()
            message_tuple = (message, priority, timestamp)
            
            # Trova posizione di inserimento
            insert_pos = len(self._queue)
            for i, (_, prio, _) in enumerate(self._queue):
                if priority > prio:
                    insert_pos = i
                    break
            
            self._queue.insert(insert_pos, message_tuple)
            
            # Aggiorna statistiche
            self._stats['messages_added'] += 1
            self._stats['max_queue_size'] = max(self._stats['max_queue_size'], len(self._queue))
            
            # Notifica thread in attesa
            self._condition.notify()
            
            return True
    
    def get(self, timeout: float = None) -> Optional[Tuple[any, int, float]]:
        """Ottiene un messaggio dalla coda (priorità più alta prima)"""
        with self._condition:
            # Attendi messaggio o timeout
            if not self._queue and not self._closed:
                if not self._condition.wait(timeout):
                    return None  # Timeout
            
            if self._closed and not self._queue:
                return None
            
            if self._queue:
                message_tuple = self._queue.popleft()
                self._stats['messages_processed'] += 1
                return message_tuple
            
            return None
    
    def get_nowait(self) -> Optional[Tuple[any, int, float]]:
        """Ottiene un messaggio senza attendere"""
        return self.get(timeout=0)
    
    def size(self) -> int:
        """Restituisce il numero di messaggi in coda"""
        with self._lock:
            return len(self._queue)
    
    def is_empty(self) -> bool:
        """Verifica se la coda è vuota"""
        with self._lock:
            return len(self._queue) == 0
    
    def clear(self) -> int:
        """Svuota la coda e restituisce il numero di messaggi rimossi"""
        with self._lock:
            size = len(self._queue)
            self._queue.clear()
            return size
    
    def close(self):
        """Chiude la coda (nessun nuovo messaggio accettato)"""
        with self._condition:
            self._closed = True
            self._condition.notify_all()
    
    def get_stats(self) -> dict:
        """Restituisce statistiche della coda"""
        with self._lock:
            stats = self._stats.copy()
            stats['current_queue_size'] = len(self._queue)
            stats['max_queue_size_limit'] = self._max_size
            stats['queue_utilization'] = len(self._queue) / self._max_size * 100
            stats['is_closed'] = self._closed
            return stats


# Utility per testing e debugging
class BufferMonitor:
    """Monitor per buffer e code con logging automatico"""
    
    def __init__(self, buffer: ThreadSafeBuffer, queue: MessageQueue = None, 
                 log_interval: int = 60):
        self.buffer = buffer
        self.queue = queue
        self.log_interval = log_interval
        self._stop_event = threading.Event()
        self._monitor_thread = None
        self.logger = logging.getLogger('BufferMonitor')
    
    def start(self):
        """Avvia il monitoraggio"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self.logger.info("Monitor buffer avviato")
    
    def stop(self):
        """Ferma il monitoraggio"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.logger.info("Monitor buffer fermato")
    
    def _monitor_loop(self):
        """Loop di monitoraggio"""
        while not self._stop_event.wait(self.log_interval):
            try:
                # Log statistiche buffer
                buffer_health = self.buffer.health_check()
                self.logger.info(f"Buffer health: {buffer_health['status']}")
                
                if buffer_health['issues']:
                    self.logger.warning(f"Buffer issues: {buffer_health['issues']}")
                
                # Log statistiche coda se presente
                if self.queue:
                    queue_stats = self.queue.get_stats()
                    self.logger.info(f"Queue size: {queue_stats['current_queue_size']}")
                    
                    if queue_stats['queue_utilization'] > 80:
                        self.logger.warning(f"Queue utilization high: {queue_stats['queue_utilization']:.1f}%")
                
            except Exception as e:
                self.logger.error(f"Errore monitor: {e}")


if __name__ == '__main__':
    # Test del buffer thread-safe
    logging.basicConfig(level=logging.INFO)
    
    # Test ThreadSafeBuffer
    buffer = ThreadSafeBuffer(max_size=1024)
    
    # Test dati di esempio
    test_data = b'\xFF\x02\xD3\x08\x31\x32\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x03'
    
    print("Test ThreadSafeBuffer:")
    buffer.extend(test_data)
    print(f"Buffer size: {buffer.size()}")
    
    frame_info = buffer.extract_frame()
    if frame_info:
        print(f"Frame estratto: {frame_info.frame.hex()}")
        print(f"Timestamp: {frame_info.timestamp}")
    
    print(f"Statistiche: {buffer.get_stats()}")
    print(f"Health check: {buffer.health_check()}")
    
    # Test MessageQueue
    print("\nTest MessageQueue:")
    queue = MessageQueue(max_size=10)
    
    # Aggiungi messaggi con diverse priorità
    queue.put("Messaggio normale", priority=1)
    queue.put("Messaggio urgente", priority=5)
    queue.put("Messaggio bassa priorità", priority=0)
    
    print(f"Queue size: {queue.size()}")
    
    # Estrai messaggi (dovrebbero uscire in ordine di priorità)
    while not queue.is_empty():
        message, priority, timestamp = queue.get_nowait()
        print(f"Messaggio: {message}, Priorità: {priority}")
    
    print(f"Statistiche coda: {queue.get_stats()}")
    
    print("\nTest completato con successo!")

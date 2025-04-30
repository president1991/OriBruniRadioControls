#!/usr/bin/env python3
"""
Script per ricevere pacchetti Meshtastic leggendo la configurazione da config.ini
e salvare i dati in un file CSV
"""
import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import json
import configparser
import logging
import sys
import time
import csv
import os
from datetime import datetime

# Carica configurazione
config = configparser.ConfigParser()
config.read('config.ini')

# Sezione Meshtastic
default_port = '/dev/ttyUSB1'
default_baud = 9600
if config.has_section('MESHTASTIC'):
    port = config.get('MESHTASTIC', 'PORT', fallback=default_port)
    baud = config.getint('MESHTASTIC', 'BAUDRATE', fallback=default_baud)
else:
    port = default_port
    baud = default_baud

# Sezione Logging
if config.has_section('LOGGING'):
    log_level_str = config.get('LOGGING', 'LEVEL', fallback='INFO')
else:
    log_level_str = 'INFO'
numeric_level = getattr(logging, log_level_str.upper(), logging.INFO)
logging.basicConfig(level=numeric_level,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Sezione Filter
topic_filter = None
log_file = None
if config.has_section('FILTER'):
    topic_filter = config.get('FILTER', 'TOPIC', fallback='').strip() or None
    log_file = config.get('FILTER', 'LOG_FILE', fallback='').strip() or None

# Sezione CSV
csv_file = 'punzonature.csv'
csv_enabled = True
if config.has_section('CSV'):
    csv_file = config.get('CSV', 'FILE', fallback=csv_file)
    csv_enabled = config.getboolean('CSV', 'ENABLED', fallback=True)
    
# Se CSV è disattivato, lo segnaliamo
if not csv_enabled:
    logging.info("Scrittura CSV disabilitata da configurazione")
    
# Directory per i file CSV (crea se non esiste)
if csv_enabled:
    csv_directory = os.path.dirname(csv_file)
    if csv_directory and not os.path.exists(csv_directory):
        os.makedirs(csv_directory)

# Se imposta un file di log separato
if log_file:
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)

# Verifica se il file CSV esiste già
csv_exists = os.path.isfile(csv_file)

# Creazione o apertura del file CSV per scrittura
def get_csv_writer():
    """Crea un nuovo writer CSV o ritorna uno esistente"""
    csv_exists = os.path.isfile(csv_file)
    file_mode = 'a' if csv_exists else 'w'  # Append se esiste, Write se nuovo
    
    csv_file_handler = open(csv_file, mode=file_mode, newline='')
    writer = csv.writer(csv_file_handler)
    
    # Scrivi intestazioni se è un nuovo file
    if not csv_exists:
        headers = [
            'timestamp',          # Timestamp locale del server
            'source_id',          # ID del dispositivo Meshtastic
            'topic',              # Topic del messaggio
            'device_time',        # Timestamp dal dispositivo
            'sicard_id',          # ID del chip/card SiCard
            'station_code',       # Codice della stazione di punzonatura
            'punch_time',         # Orario della punzonatura
            'device_name',        # Nome del dispositivo
            'extra_data'          # Altri dati in JSON
        ]
        writer.writerow(headers)
        logging.info(f"Creato nuovo file CSV: {csv_file}")
    
    return writer, csv_file_handler

# Callback per i pacchetti ricevuti (solo TEXT_MESSAGE_APP)
def on_receive(packet, interface=None):
    """
    packet: dict con chiavi 'decoded', 'text', 'topic', etc.
    """
    decoded = packet.get('decoded') or {}
    # Filtro per applicazioni di testo
    if decoded.get('portnum') != 'TEXT_MESSAGE_APP':
        return

    payload = decoded.get('payload')
    topic = packet.get('topic', 'unknown')
    device_time = packet.get('time', 0)
    src = packet.get('from', 'unknown')
    
    # Converte il timestamp in formato leggibile
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Filtro per topic
    if topic_filter and topic != topic_filter:
        return

    # Se l'opzione CSV è disabilitata, procedi solo con il logging
    writer = None
    file_handler = None
    if csv_enabled:
        # Apre il file CSV per scrittura
        writer, file_handler = get_csv_writer()
    
    try:
        # Se c'è payload JSON
        if payload:
            try:
                raw = payload.decode() if isinstance(payload, (bytes, bytearray)) else payload
                data = json.loads(raw)
                
                # Log normale
                logging.info(f"[{src}] TOPIC={topic} TIME={device_time}")
                for k, v in data.items():
                    logging.info(f"  {k}: {v}")
                
                # Estrai i dati specifici per la punzonatura
                device_name = data.get('name', 'unknown')
                
                # Estrai campi specifici per SiCard (sportident)
                sicard_id = data.get('sicard_id', data.get('card_id', data.get('chip_id', 'unknown')))
                station_code = data.get('station_code', data.get('station_id', data.get('control_code', 'unknown')))
                punch_time = data.get('punch_time', data.get('time', device_time))
                
                # Salva su CSV se abilitato
                if csv_enabled:
                    # Crea un dizionario con tutti i dati extra
                    extra_fields = ['name', 'sicard_id', 'card_id', 'chip_id', 'station_code', 
                                   'station_id', 'control_code', 'punch_time', 'time']
                    extra_data = {k: v for k, v in data.items() if k not in extra_fields}
                    extra_json = json.dumps(extra_data) if extra_data else '{}'
                    
                    # Scrivi su CSV
                    writer.writerow([
                        timestamp,
                        src,
                        topic,
                        device_time,
                        sicard_id,
                        station_code,
                        punch_time,
                        device_name,
                        extra_json
                    ])
                    
                    logging.info(f"Salvata punzonatura nel CSV: SiCard {sicard_id}, Stazione {station_code}")
                
            except json.JSONDecodeError:
                # Non è JSON, salva come testo semplice
                raw_text = payload.decode() if isinstance(payload, (bytes, bytearray)) else str(payload)
                if csv_enabled:
                    writer.writerow([timestamp, src, topic, device_time, 'unknown', 'unknown', 'unknown', 'unknown', raw_text])
                logging.info(f"[{src}] PAYLOAD non JSON: {raw_text}")
        
        # Fallback su testo plain
        elif packet.get('text'):
            text = packet.get('text')
            if csv_enabled:
                writer.writerow([timestamp, src, topic, device_time, 'unknown', 'unknown', 'unknown', 'unknown', text])
            logging.info(f"[{src}] RAW: {text}")
        
        else:
            packet_str = str(packet)
            if csv_enabled:
                writer.writerow([timestamp, src, topic, device_time, 'unknown', 'unknown', 'unknown', 'unknown', packet_str])
            logging.info(f"[{src}] PACKET: {packet_str}")
    
    except Exception as e:
        logging.error(f"Errore durante l'elaborazione del pacchetto: {e}")
    
    finally:
        # Chiudi il file per assicurarsi che i dati vengano scritti
        if csv_enabled and file_handler:
            file_handler.flush()
            file_handler.close()


def main():
    print(f"Aprendo Meshtastic su {port} @ {baud}bps…")
    try:
        iface = meshtastic.serial_interface.SerialInterface(devPath=port)
    except Exception as e:
        logging.error(f"Impossibile aprire interfaccia Meshtastic: {e}")
        sys.exit(1)

    # Sottoscrivi il callback per i messaggi ricevuti
    pub.subscribe(on_receive, 'meshtastic.receive')

    if csv_enabled:
        print(f"In ascolto di messaggi. Le punzonature verranno salvate in {csv_file}")
    else:
        print("In ascolto di messaggi. Registrazione CSV disabilitata.")
    print("Ctrl+C per uscire.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nChiusura interfaccia Meshtastic…")
    finally:
        iface.close()

if __name__ == '__main__':
    main()
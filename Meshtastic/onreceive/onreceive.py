#!/usr/bin/env python3
"""
Script per ricevere pacchetti Meshtastic leggendo la configurazione da config.ini
e salvare i dati di punzonatura in un file CSV
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

def receive_packet():
    """
    Funzione wrapper che gestisce la ricezione dei pacchetti da Meshtastic.
    Utilizzato per mantenere compatibilità con il codice originale.
    """
    # Questa funzione non viene utilizzata direttamente, dal momento che utilizziamo
    # i callback di Meshtastic, ma esiste per documentazione e possibile uso futuro
    raise NotImplementedError("Questa funzione non viene utilizzata direttamente - i pacchetti sono gestiti via callback")

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
    topic = packet.get('topic', '')
    device_time = packet.get('time', '')
    src = packet.get('from', '')
    
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
                
                # Parse del JSON - versione migliorata dal primo script
                if raw and raw.strip().startswith('{'):
                    try:
                        data = json.loads(raw)
                        
                        # Log normale
                        # Log con informazioni più rilevanti
                        card_number = data.get('card_number', '')
                        control = data.get('control', '')
                        punch_time_val = data.get('punch_time', '')
                        station_name = data.get('name', '')
                        
                        logging.info(f"[{src}] PUNCH: SiCard={card_number}, Control={control}, Time={punch_time_val}, Station={station_name}")
                        
                        # Log dettagliato per debug
                        if logging.getLogger().level <= logging.DEBUG:
                            for k, v in data.items():
                                logging.debug(f"  {k}: {v}")
                        
                        # Estrai i campi dal JSON (compatibile con entrambi gli script)
                        device_name = data.get('name', '')
                        
                        # Supporto per diversi nomi di campo per l'ID della carta
                        # Priorità a card_number che contiene il numero effettivo della SiCard
                        sicard_id = data.get('card_number',
                                        data.get('sicard_id',
                                        data.get('card_id',
                                        data.get('chip_id', ''))))
                        
                        # Supporto per diversi nomi di campo per il codice stazione
                        station_code = data.get('control',
                                            data.get('station_code',
                                            data.get('station_id',
                                            data.get('control_code', ''))))
                        
                        # Supporto per diversi nomi di campo per l'orario di punzonatura
                        punch_time = data.get('punch_time',
                                         data.get('time', ''))
                        
                        if csv_enabled:
                            # Conserva il JSON originale come extra data
                            extra_json = raw
                            
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
                            
                            logging.info(f"Salvata punzonatura nel CSV: SiCard {sicard_id}, Stazione {station_code}, Ora {punch_time}")
                    
                    except json.JSONDecodeError:
                        # Fallback se non è JSON valido
                        logging.warning("JSON non valido, scrittura fallback come testo")
                        raw_text = raw
                        if csv_enabled:
                            writer.writerow([timestamp, src, topic, device_time, '', '', '', '', raw_text])
                else:
                    # Non è JSON, trattalo come testo semplice
                    raw_text = payload.decode() if isinstance(payload, (bytes, bytearray)) else str(payload)
                    if csv_enabled:
                        writer.writerow([timestamp, src, topic, device_time, '', '', '', '', raw_text])
                    logging.info(f"[{src}] PAYLOAD non JSON: {raw_text}")
            
            except Exception as e:
                logging.error(f"Errore nel processare il payload: {e}")
                if csv_enabled:
                    writer.writerow([timestamp, src, topic, device_time, '', '', '', '', str(e)])
        
        # Fallback su testo plain
        elif packet.get('text'):
            text = packet.get('text')
            if csv_enabled:
                writer.writerow([timestamp, src, topic, device_time, '', '', '', '', text])
            logging.info(f"[{src}] RAW: {text}")
        
        else:
            packet_str = str(packet)
            if csv_enabled:
                writer.writerow([timestamp, src, topic, device_time, '', '', '', '', packet_str])
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
#!/usr/bin/env python3
"""
Script di esempio per ricevere pacchetti Meshtastic leggendo la configurazione da config.ini
"""
import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import json
import configparser
import logging
import sys
import time

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

# Se imposta un file di log separato
if log_file:
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)

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
    topic = packet.get('topic')
    ts = packet.get('time')
    src = packet.get('from')

    # Filtro per topic
    if topic_filter and topic != topic_filter:
        return

    # Se c'è payload JSON
    if payload:
        try:
            raw = payload.decode() if isinstance(payload, (bytes, bytearray)) else payload
            data = json.loads(raw)
            logging.info(f"[{src}] TOPIC={topic} TIME={ts}")
            for k, v in data.items():
                logging.info(f"  {k}: {v}")
        except Exception:
            logging.info(f"[{src}] PAYLOAD non JSON: {payload}")
    # Fallback su testo plain
    elif packet.get('text'):
        logging.info(f"[{src}] RAW: {packet.get('text')}")
    else:
        logging.info(f"[{src}] PACKET: {packet}")


def main():
    print(f"Aprendo Meshtastic su {port} @ {baud}bps…")
    try:
        iface = meshtastic.serial_interface.SerialInterface(devPath=port)
    except Exception as e:
        logging.error(f"Impossibile aprire interfaccia Meshtastic: {e}")
        sys.exit(1)

    # Sottoscrivi il callback per i messaggi ricevuti
    pub.subscribe(on_receive, 'meshtastic.receive')

    print("In ascolto di messaggi. Ctrl+C per uscire.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nChiusura interfaccia Meshtastic…")
    finally:
        iface.close()

if __name__ == '__main__':
    main()
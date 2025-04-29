#!/usr/bin/env python3
"""
Script di esempio per ricevere pacchetti Meshtastic leggendo la configurazione da config.ini
"""
import meshtastic
import meshtastic.serial_interface
import json
import configparser
import logging
import sys
import time

# Carica configurazione
config = configparser.ConfigParser()
config.read('config.ini')

# Sezione Meshtastic
mesh_conf = config['MESHTASTIC']
port = mesh_conf.get('PORT', '/dev/ttyUSB1')
baud = mesh_conf.getint('BAUDRATE', 9600)

# Sezione Logging
log_conf = config.get('LOGGING', {})
log_level_str = log_conf.get('LEVEL', 'INFO')
numeric_level = getattr(logging, log_level_str.upper(), logging.INFO)
logging.basicConfig(level=numeric_level,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Sezione Filter
filter_conf = config.get('FILTER', {})
topic_filter = filter_conf.get('TOPIC', '').strip() or None
log_file = filter_conf.get('LOG_FILE', '').strip() or None

# Se imposta un file di log separato
if log_file:
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)


def on_receive(packet):
    """
    Callback invocata per ciascun pacchetto ricevuto.
    packet: dict con chiavi 'from', 'text', 'topic', 'time', 'wantAck', ...
    """
    src = packet.get('from')
    text = packet.get('text')
    topic = packet.get('topic')
    ts = packet.get('time')  # UNIX epoch
    # Filtro per topic se specificato
    if topic_filter and topic != topic_filter:
        return

    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        # Non è JSON: logga raw
        logging.info(f"[{src}] RAW: {text}")
    else:
        # È JSON: logga i campi
        logging.info(f"[{src}] TOPIC={topic} TIME={ts}")
        for k, v in data.items():
            logging.info(f"  {k}: {v}")


def main():
    print(f"Aprendo Meshtastic su {port} @ {baud}bps…")
    try:
        iface = meshtastic.serial_interface.SerialInterface(port, baud)
    except Exception as e:
        logging.error(f"Impossibile aprire interfaccia Meshtastic: {e}")
        sys.exit(1)

    # Registra callback
    iface.onReceive(on_receive)

    print("In ascolto di messaggi. Ctrl+C per uscire.")
    try:
        # Loop leggero per mantenere viva l'interfaccia
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nChiusura interfaccia Meshtastic…")
    finally:
        iface.close()


if __name__ == '__main__':
    main()

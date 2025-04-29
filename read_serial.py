#!/usr/bin/env python3
"""
Script ottimizzato per lettura Sportident da seriale, invio punzonature via Internet e via Meshtastic.
Versione ottimizzata per Raspberry Pi con gestione efficiente delle risorse e del consumo energetico.
"""

import logging
import time
import json
import signal
import os
import configparser
import gzip
import serial
import threading
import sys
import psutil
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import mysql.connector
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from construct import *
import meshtastic
import meshtastic.serial_interface

# Variabili globali per gestione risorse
executor = None
serial_port = None
session = None
mesh_iface = None
shutdown_event = threading.Event()
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

# --------------------------
# CARICAMENTO CONFIGURAZIONE
# --------------------------
def load_config():
    """Carica configurazione da file esterno o crea default se non esiste"""
    config = configparser.ConfigParser()
    # Crea directory logs se non esiste
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    # Configurazione di default
    if not os.path.exists(config_path):
        config['SERIAL'] = {
            'PORT': '/dev/ttyUSB0',
            'BAUDRATE': '38400',
            'POLL_SERIAL_MS': '10'
        }
        config['DATABASE'] = {
            'USER': 'root',
            'PASSWORD': 'PuhA7gWCrW',
            'HOST': 'localhost',
            'DATABASE': 'OriBruniRadioControls'
        }
        config['REMOTE'] = {
            'URL': 'https://orienteering.services/radiocontrol/receive_data.php',
            'MAX_RETRIES': '3',
            'BACKOFF_FACTOR': '0.5',
            'TIMEOUT': '5'
        }
        config['LOGGING'] = {
            'LEVEL': 'INFO',
            'MAX_SIZE_MB': '5',
            'BACKUP_COUNT': '3'
        }
        config['EXECUTION'] = {
            'MAX_WORKERS': '3',
            'WATCHDOG_INTERVAL': '60'
        }
        config['RASPBERRY'] = {
            'OPTIMIZE_POWER': 'true',
            'CPU_LIMIT': '80',
            'NETWORK_TIMEOUT': '30',
            'KEEP_ALIVE_INTERVAL': '300'
        }
        config['MESHTASTIC'] = {
            'PORT': '/dev/ttyUSB1',
            'BAUDRATE': '9600',
            'TOPIC': 'punch_data',
            'ACK': 'true'
        }
        # Scrivi il file di configurazione
        with open(config_path, 'w') as f:
            config.write(f)
        print(f"File di configurazione creato in {config_path}. Modifica i valori e riavvia.")
    config.read(config_path)
    return config

# --------------------------
# SETUP LOGGING
# --------------------------
def setup_logging(config):
    """Configura sistema di logging con rotazione file"""
    log_level = getattr(logging, config['LOGGING'].get('LEVEL', 'INFO'))
    max_size = int(config['LOGGING'].get('MAX_SIZE_MB', '5')) * 1024 * 1024
    backup_count = int(config['LOGGING'].get('BACKUP_COUNT', '3'))
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_file = os.path.join(log_path, 'sportident.log')
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_size, backupCount=backup_count)
    file_handler.setFormatter(log_formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    logging.info("Logging configurato con livello %s", config['LOGGING'].get('LEVEL'))

# --------------------------
# SESSIONE HTTP OTTIMIZZATA
# --------------------------
def create_http_session(config):
    """Crea una sessione HTTP ottimizzata per connessioni instabili"""
    global session
    if session:
        try: session.close()
        except: pass
    session = requests.Session()
    retries = int(config['REMOTE'].get('MAX_RETRIES', '3'))
    backoff = float(config['REMOTE'].get('BACKOFF_FACTOR', '0.5'))
    timeout = int(config['REMOTE'].get('TIMEOUT', '5'))
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST", "GET"]
    )
    adapter = HTTPAdapter(
        pool_connections=1,
        pool_maxsize=2,
        max_retries=retry_strategy
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent":      "OriBruniClient/1.0",
        "Accept":          "application/json",
        "Accept-Encoding": "gzip",
        "Connection":      "keep-alive",
        "Content-Type":    "application/json"
    })
    return session

# --------------------------
# SESSIONE MESHTASTIC
# --------------------------
def create_mesh_session(config):
    """Crea e ritorna una connessione Meshtastic via seriale"""
    global mesh_iface
    if mesh_iface:
        try: mesh_iface.close()
        except: pass
    port = config['MESHTASTIC']['PORT']
    baud = int(config['MESHTASTIC'].get('BAUDRATE', '9600'))
    mesh_iface = meshtastic.serial_interface.SerialInterface(port, baud)
    return mesh_iface

# --------------------------
# PARSING SPORTIDENT
# --------------------------
def remove_dle(data: bytes) -> bytes:
    """Rimuove caratteri DLE dalla sequenza di byte"""
    result = bytearray()
    skip = False
    for b in data:
        if skip:
            result.append(b)
            skip = False
        elif b == 0x10:
            skip = True
        else:
            result.append(b)
    return bytes(result)

class SportidentTimeAdapter(Adapter):
    def _decode(self, obj, context, path):
        seconds = Int16ub.parse(obj)
        return timedelta(seconds=seconds)
    def _encode(self, obj, context, path): raise NotImplementedError()
SportidentTime = SportidentTimeAdapter(Bytes(2))

class CorrectedSportidentCardAdapter(Adapter):
    def _decode(self, obj, context, path):
        buf = bytes(obj[:4])
        if buf[0] == 0x00:
            prefix = buf[1]
            rem = int.from_bytes(buf[2:4], 'big')
            num5 = prefix * 100000 + rem
            if 100000 < num5 < 500000 and 1 <= prefix <= 9:
                return num5
        return int.from_bytes(buf[1:4], 'big')
    def _encode(self, obj, context, path): raise NotImplementedError()
CorrectedSportidentCard = CorrectedSportidentCardAdapter(Bytes(4))

SiPacket = Struct(
    "Wakeup"  / Optional(Const(b"\xFF")),
    "Stx"     / Const(b"\x02"),
    "Command" / Const(b"\xD3"),
    "Len"     / Int8ub,
    "Cn_high" / Int8ub,
    "Cn_low"  / Int8ub,
    "SiNr"    / CorrectedSportidentCard,
    "Td"      / Int8ub,
    "ThTl"    / SportidentTime,
    "Tsubsec" / Int8ub,
    "Mem"     / Int24ub,
    "Crc1"    / Int8ub,
    "Crc2"    / Int8ub,
    "Etx"     / Const(b"\x03")
)

def convert_extended_time(td_byte: int, th_tl: timedelta, tss_byte: int):
    half_day = td_byte & 0x01
    secs = th_tl.total_seconds() + (12*3600 if half_day else 0) + tss_byte/256.0
    return secs

def extract_frame(buffer: bytearray):
    while buffer and buffer[0] == 0xFF:
        buffer.pop(0)
    try:
        start = buffer.index(0x02)
    except ValueError:
        return None, buffer
    if len(buffer)-start < 3:
        return None, buffer
    length = buffer[start+2]
    total = length + 6
    if len(buffer)-start < total:
        return None, buffer
    frame = bytes(buffer[start:start+total])
    newbuf = buffer[start+total:]
    if frame[-1] != 0x03:
        logging.error("Frame errato: %s", frame.hex())
        return None, newbuf
    return frame, newbuf

def decode_sportident(raw: bytes):
    if not (raw.startswith(b"\x02") and raw.endswith(b"\x03")):
        return None
    body = remove_dle(raw[1:-1])
    try:
        p = SiPacket.parse(body)
        secs = convert_extended_time(p.Td, p.ThTl, p.Tsubsec)
        base = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        dt = base + timedelta(seconds=secs)
        return {
            'control': p.Cn_low,
            'card_number': p.SiNr,
            'punch_time': dt,
            'raw_punch_data': raw.hex()
        }
    except Exception as e:
        logging.error("Parse error: %s", e)
        return None

# --------------------------
# FUNZIONI DATABASE
# --------------------------
def get_db_connection(db_config):
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as e:
        logging.error("DB conn error: %s", e)
        return None

def insert_into_db(parsed, db_config):
    conn = get_db_connection(db_config)
    if not conn:
        return None
    cur = conn.cursor()
    q = ("""
    INSERT INTO radiocontrol (
      control, card_number, punch_time,
      raw_punch_data, timestamp, sent_internet
    ) VALUES (%s,%s,%s,%s,%s,0)
    """)
    vals = (
        parsed['control'], parsed['card_number'],
        parsed['punch_time'].strftime('%Y-%m-%d %H:%M:%S.%f'),
        parsed['raw_punch_data'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    try:
        with threading.Lock():
            cur.execute(q, vals)
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        logging.error("DB insert error: %s", e)
    finally:
        cur.close(); conn.close()
    return None

def fetch_record_by_id(record_id, db_config):
    conn = get_db_connection(db_config)
    if not conn:
        return None
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM radiocontrol WHERE id=%s", (record_id,))
            return cur.fetchone()
    except mysql.connector.Error as e:
        logging.error("Fetch error: %s", e)
    finally:
        conn.close()
    return None

def get_unsent_records(db_config, limit=10):
    conn = get_db_connection(db_config)
    if not conn:
        return []
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute("SELECT * FROM radiocontrol WHERE sent_internet=0 ORDER BY id ASC LIMIT %s", (limit,))
            return cur.fetchall()
    except mysql.connector.Error as e:
        logging.error("Fetch unsent error: %s", e)
    finally:
        conn.close()
    return []

def mark_record_as_sent(record_id, db_config):
    conn = get_db_connection(db_config)
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE radiocontrol SET sent_internet=1 WHERE id=%s", (record_id,))
            conn.commit()
            return True
    except mysql.connector.Error as e:
        logging.error("Mark sent error: %s", e)
    finally:
        conn.close()
    return False

def get_device_identifiers(db_config):
    conn = get_db_connection(db_config)
    if not conn:
        return None, None
    cur = conn.cursor()
    cur.execute("SELECT nome, valore FROM costanti WHERE nome IN ('nome','pkey') ORDER BY nome")
    rows = cur.fetchall()
    cur.close(); conn.close()
    if len(rows) == 2:
        d = {r[0]: r[1] for r in rows}
        return d.get('nome'), d.get('pkey')
    logging.error("Device IDs mancanti")
    return None, None

def log_event(nome, errore, descr, db_config):
    conn = get_db_connection(db_config)
    if not conn:
        return
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO log(nome, errore, descrizione) VALUES(%s,%s,%s)",
                    (nome, errore, descr))
        conn.commit()
    except mysql.connector.Error as e:
        logging.error("Log error: %s", e)
    finally:
        cur.close(); conn.close()

# --------------------------
# INVIO VIA MESHTASTIC
# --------------------------
def send_record_on_mesh(record, name, pkey, config, mesh_iface):
    """Invia il record sulla mesh Meshtastic"""
    if not mesh_iface or not record:
        return False
    payload = {
        'name': name,
        'pkey': pkey,
        'id': record['id'],
        'control': record['control'],
        'card_number': record['card_number'],
        'punch_time': record['punch_time'].isoformat()
    }
    topic = config['MESHTASTIC'].get('TOPIC', '') or None
    want_ack = config['MESHTASTIC'].getboolean('ACK', True)
    try:
        mesh_iface.sendText(
            json.dumps(payload),
            topic_name=topic,
            wantAck=want_ack
        )
        logging.info("Inviato su Meshtastic id=%s", record['id'])
        return True
    except Exception as e:
        logging.error("Errore invio Mesh %s: %s", record['id'], e)
        return False

# --------------------------
# INVIO RECORD ONLINE + MESH
# --------------------------
def send_record_online(record, config, session, db_config):
    """Invia un record al servizio online e su Meshtastic"""
    if not record:
        return False
    record_id = record.get('id')
    name, pkey = get_device_identifiers(db_config)
    if not name or not pkey:
        logging.error("Device IDs mancanti per %s", record_id)
        return False
    # Prepara payload HTTP
    punch_time = record['punch_time']
    timestamp = record['timestamp']
    if isinstance(punch_time, datetime):
        punch_time = punch_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    if isinstance(timestamp, datetime):
        timestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    payload = {
        'name': name,
        'pkey': pkey,
        'id': record_id,
        'control': record['control'],
        'card_number': record['card_number'],
        'punch_time': punch_time,
        'timestamp': timestamp
    }
    try:
        resp = session.post(config['REMOTE'].get('URL'), json=payload,
                             timeout=int(config['REMOTE'].get('TIMEOUT', '5')))
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') == 'success':
            logging.info("Inviato online id=%s", record_id)
            mark_record_as_sent(record_id, db_config)
            log_event(name, 'Successo', f'id={record_id}', db_config)
        else:
            logging.error("Errore invio %s: %s", record_id, data)
            log_event(name, 'Errore Invio', str(data), db_config)
    except requests.RequestException as e:
        logging.error("HTTP error %s: %s", record_id, e)
        log_event(name, 'Errore Connessione', str(e), db_config)
    # Invia anche su Meshtastic
    try:
        send_record_on_mesh(record, name, pkey, config, mesh_iface)
    except Exception:
        pass
    return True

# --------------------------
# PROCESS RECORD
# --------------------------
def process_record(record_id, config, session, db_config):
    record = fetch_record_by_id(record_id, db_config)
    if record:
        send_record_online(record, config, session, db_config)

# --------------------------
# MONITORAGGIO SISTEMA
# --------------------------
def check_system_health():
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        temp = None
        if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read()) / 1000.0
        health_data = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'disk_percent': disk_percent,
            'temperature': temp
        }
        if temp and temp > 80:
            logging.warning("Temperatura CPU elevata: %.1f°C", temp)
        if cpu_percent > 90:
            logging.warning("Utilizzo CPU elevato: %.1f%%", cpu_percent)
        return health_data
    except Exception as e:
        logging.error("Errore monitoraggio sistema: %s", e)
        return None

# --------------------------
# KEEP ALIVE E WATCHDOG
# --------------------------
def keep_alive_task(config, db_config):
    if shutdown_event.is_set():
        return
    try:
        name, pkey = get_device_identifiers(db_config)
        health = check_system_health()
        payload = {
            'name': name,
            'pkey': pkey,
            'action': 'keepalive',
            'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            'system_status': health
        }
        remote_url = config['REMOTE'].get('URL').replace('receive_data.php', 'keepalive.php')
        resp = session.post(remote_url, json=payload,
                             timeout=int(config['REMOTE'].get('TIMEOUT', '5')))
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') == 'success':
            logging.debug("Keep-alive inviato con successo")
        else:
            logging.warning("Errore keep-alive: %s", data)
    except Exception as e:
        logging.error("Errore keep-alive: %s", e)
    if not shutdown_event.is_set():
        interval = int(config['RASPBERRY'].get('KEEP_ALIVE_INTERVAL', '300'))
        threading.Timer(interval, keep_alive_task, args=[config, db_config]).start()

def retry_unsent_records(config, db_config):
    if shutdown_event.is_set():
        return
    try:
        unsent = get_unsent_records(db_config)
        if unsent:
            logging.info("Trovati %d record non inviati", len(unsent))
            for record in unsent:
                if shutdown_event.is_set(): break
                send_record_online(record, config, session, db_config)
    except Exception as e:
        logging.error("Errore retry unsent: %s", e)
    if not shutdown_event.is_set():
        threading.Timer(300, retry_unsent_records, args=[config, db_config]).start()

# --------------------------
# SEGNALI
# --------------------------
def setup_signal_handlers():
    def signal_handler(sig, frame):
        logging.info("Segnale %s ricevuto, chiusura in corso...", sig)
        shutdown_event.set()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

# --------------------------
# OTTIMIZZAZIONE RASPBERRY PI
# --------------------------
def optimize_raspberry_pi(config):
    if config['RASPBERRY'].getboolean('OPTIMIZE_POWER', True):
        try:
            for led_path in ['/sys/class/leds/led0/brightness', '/sys/class/leds/led1/brightness']:
                if os.path.exists(led_path) and os.access(led_path, os.W_OK):
                    with open(led_path, 'w') as f: f.write('0')
            gov = '/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'
            if os.path.exists(gov):
                with open(gov, 'w') as f: f.write('powersave')
            logging.info("Ottimizzazione energia Raspberry Pi completata")
        except Exception as e:
            logging.warning("Impossibile ottimizzare energia Raspberry Pi: %s", e)

# --------------------------
# MAIN LOOP
# --------------------------
def main_loop(config):
    global executor, serial_port, session, mesh_iface
    db_config = {
        'user': config['DATABASE']['USER'],
        'password': config['DATABASE']['PASSWORD'],
        'host': config['DATABASE']['HOST'],
        'database': config['DATABASE']['DATABASE']
    }
    session = create_http_session(config)
    mesh_iface = create_mesh_session(config)
    logging.info("Mesh session aperta su %s", config['MESHTASTIC']['PORT'])
    optimize_raspberry_pi(config)
    max_workers = int(config['EXECUTION'].get('MAX_WORKERS', '3'))
    executor = ThreadPoolExecutor(max_workers=max_workers)
    threading.Timer(10, keep_alive_task, args=[config, db_config]).start()
    threading.Timer(30, retry_unsent_records, args=[config, db_config]).start()
    try:
        port = config['SERIAL']['PORT']
        baudrate = int(config['SERIAL']['BAUDRATE'])
        serial_port = serial.Serial(port, baudrate, timeout=0.1)
        logging.info("Porta seriale %s aperta a %d baud", port, baudrate)
    except Exception as e:
        logging.critical("Errore apertura seriale: %s", e)
        shutdown_event.set()
        return
    poll_interval = float(config['SERIAL'].get('POLL_SERIAL_MS', '10')) / 1000.0
    recv_buffer = bytearray()
    logging.info("Loop principale avviato")
    while not shutdown_event.is_set():
        try:
            data = serial_port.read(200)
            if data:
                recv_buffer.extend(data)
                while True:
                    frame, recv_buffer = extract_frame(recv_buffer)
                    if not frame: break
                    pkt = decode_sportident(frame)
                    if not pkt: continue
                    last_id = insert_into_db(pkt, db_config)
                    if last_id:
                        print(f"Station (Control): {pkt['control']}")
                        print(f"Chip number: {pkt['card_number']}")
                        print(f"Punch time: {pkt['punch_time']}")
                        print("-" * 20)
                        executor.submit(process_record, last_id, config, session, db_config)
                    else:
                        logging.error("Inserimento DB fallito per %s", pkt)
            else:
                time.sleep(poll_interval)
        except Exception as e:
            logging.error("Errore loop principale: %s", e)
            time.sleep(1)
    logging.info("Chiusura risorse in corso...")
    if serial_port and serial_port.is_open:
        serial_port.close()
        logging.info("Porta seriale chiusa")
    if executor:
        logging.info("Attesa completamento tasks...")
        executor.shutdown(wait=True)
        logging.info("Thread pool chiuso")
    if session:
        session.close()
        logging.info("Sessione HTTP chiusa")
    if mesh_iface:
        try: mesh_iface.close()
        except: pass
        logging.info("Sessione Meshtastic chiusa")
    logging.info("Programma terminato correttamente")

# --------------------------
# SERVICE FILE
# --------------------------
def create_service_file():
    script_path = os.path.abspath(__file__)
    service_content = f"""[Unit]
Description=Sportident Reader Service
After=network.target mysql.service

[Service]
User=pi
WorkingDirectory={os.path.dirname(script_path)}
ExecStart=/usr/bin/python3 {script_path}
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=sportident
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
    service_path = os.path.join(os.path.dirname(script_path), 'sportident.service')
    with open(service_path, 'w') as f:
        f.write(service_content)
    print(f"File di servizio creato in {service_path}")
    print("Per installare il servizio:")
    print(f"sudo cp {service_path} /etc/systemd/system/")
    print("sudo systemctl daemon-reload")
    print("sudo systemctl enable sportident.service")
    print("sudo systemctl.start sportident.service")

# --------------------------
# ENTRY POINT
# --------------------------
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == "--create-service":
        create_service_file()
        sys.exit(0)
    config = load_config()
    setup_logging(config)
    setup_signal_handlers()
    try:
        main_loop(config)
    except Exception as e:
        logging.critical("Errore fatale: %s", e, exc_info=True)
        sys.exit(1)

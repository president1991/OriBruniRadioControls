#!/usr/bin/env python3
"""
Script ottimizzato per lettura Sportident da seriale e invio punzonature via Internet.
Riduce il traffico di rete con keep-alive, gzip, header minimi.
"""

import logging
import time
import json
import gzip
import serial
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import mysql.connector
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from construct import *

# --------------------------
# CONFIGURAZIONE GENERALE
# --------------------------
SERIAL_PORT    = '/dev/ttyUSB0'
BAUDRATE       = 38400
POLL_SERIAL_MS = 10  # ms tra letture seriale
REMOTE_URL     = "https://orienteering.services/radiocontrol/receive_data.php"
DB_CONFIG = {
    'user':     'root',
    'password': 'PuhA7gWCrW',
    'host':     'localhost',
    'database': 'OriBruniRadioControls'
}

# --------------------------
# LOGGER
# --------------------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --------------------------
# SESSIONE HTTP OTTIMIZZATA
# --------------------------
SESSION = requests.Session()
adapter = HTTPAdapter(
    pool_connections=2,
    pool_maxsize=2,
    max_retries=Retry(total=2, backoff_factor=0.5,
                       status_forcelist=[500,502,503,504])
)
SESSION.mount("https://", adapter)
SESSION.headers.update({
    "User-Agent":      "OriBruniClient/1.0",
    "Accept":          "application/json",
    "Accept-Encoding": "gzip",
    "Connection":      "keep-alive",
    "Content-Type":    "application/json"
})

# --------------------------
# PARSING SPORTIDENT
# --------------------------
def remove_dle(data: bytes) -> bytes:
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
    def _encode(self, obj, context, path):
        raise NotImplementedError()
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
    def _encode(self, obj, context, path):
        raise NotImplementedError()
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

# --------------------------
# FRAME EXTRACTION
# --------------------------
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

# --------------------------
# DECODIFICA PACCHETTO
# --------------------------
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
def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        logging.error("DB conn error: %s", e)
        return None

def insert_into_db(parsed):
    conn = get_db_connection()
    if not conn:
        return None
    cur = conn.cursor()
    q = ("""
    INSERT INTO radiocontrol (
      control, card_number, punch_time,
      raw_punch_data, timestamp, sent_internet
    ) VALUES (%s,%s,%s,%s,%s,0)
    """
    )
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

def fetch_record_by_id(record_id):
    conn = get_db_connection()
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

def get_device_identifiers():
    conn = get_db_connection()
    if not conn:
        return None, None
    cur = conn.cursor()
    cur.execute("SELECT nome, valore FROM costanti WHERE nome IN ('nome','pkey') ORDER BY nome")
    rows = cur.fetchall()
    cur.close(); conn.close()
    if len(rows) == 2:
        d = {r[0]: r[1] for r in rows}
        return d['nome'], d['pkey']
    logging.error("Device IDs mancanti")
    return None, None

def log_event(nome, errore, descr):
    conn = get_db_connection()
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
# INVIO RECORD ONLINE OTTIMIZZATO
# --------------------------
def send_record_online(record):
    record_id = record.get('id')
    name, pkey = get_device_identifiers()
    if not name or not pkey:
        logging.error("Device IDs mancanti per %s", record_id)
        return
    payload = {
        'name': name,
        'pkey': pkey,
        'id': record_id,
        'control': record['control'],
        'card_number': record['card_number'],
        'punch_time': record['punch_time'].strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        'timestamp': record['timestamp']
    }
    try:
        resp = SESSION.post(REMOTE_URL, json=payload, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') == 'success':
            logging.info("Inviato online id=%s", record_id)
            log_event(name, 'Successo', f'id={record_id}')
        else:
            logging.error("Errore invio %s: %s", record_id, data)
            log_event(name, 'Errore Invio', str(data))
    except requests.RequestException as e:
        logging.error("HTTP error %s: %s", record_id, e)
        log_event(name, 'Errore Connessione', str(e))

# --------------------------
# LOOP PRINCIPALE
# --------------------------
def main_loop():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.1)
        logging.info("Porta seriale %s aperta a %d baud", SERIAL_PORT, BAUDRATE)
    except Exception as e:
        logging.critical("Errore apertura seriale: %s", e)
        return

    recv_buffer = bytearray()
    executor    = ThreadPoolExecutor(max_workers=5)

    while True:
        data = ser.read(200)
        if data:
            recv_buffer.extend(data)
            while True:
                frame, recv_buffer = extract_frame(recv_buffer)
                if not frame:
                    break
                pkt = decode_sportident(frame)
                if not pkt:
                    continue
                last_id = insert_into_db(pkt)
                if last_id:
                    executor.submit(lambda rid=last_id: send_record_online(fetch_record_by_id(rid)))
                else:
                    logging.error("Inserimento DB fallito per %s", pkt)
        else:
            time.sleep(POLL_SERIAL_MS/1000.0)

if __name__ == '__main__':
    main_loop()

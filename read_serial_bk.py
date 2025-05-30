#!/usr/bin/env python3
"""
Script di lettura dalla porta seriale che usa Construct per parsare i pacchetti Sportident
e stampa i dati essenziali: station (control), SI card number (chip number) e punch_time.
Il punch_time viene calcolato usando la data di oggi (alla mezzanotte) combinata con
l'orario derivato dal pacchetto.
CRC e controllo dei dati vengono ignorati.
Ogni punzonatura ricevuta viene inviata via internet.
"""

from construct import *
from datetime import datetime, timedelta
import serial
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
import mysql.connector
import requests
import sys
import json

# Configura il logger
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Configurazione del database locale
db_config = {
    'user': 'root',
    'password': 'PuhA7gWCrW',
    'host': 'localhost',
    'database': 'OriBruniRadioControls'
}

# URL del servizio remoto
REMOTE_URL = "https://orienteering.services/radiocontrol/receive_data.php"

# --------------------------
# Funzione remove_dle
# --------------------------
def remove_dle(data: bytes) -> bytes:
    result = bytearray()
    skip = False
    for i, b in enumerate(data):
        if skip:
            result.append(b)
            skip = False
        elif b == 0x10:
            # Se il byte successivo è 0x03, interpreta come dato letterale 0x03
            if i + 1 < len(data) and data[i + 1] == 0x03:
                result.append(0x03)
                skip = True
            else:
                skip = True
        else:
            result.append(b)
    return bytes(result)

# --------------------------
# Parser Construct per Sportident
# --------------------------
class SportidentTimeAdapter(Adapter):
    def _decode(self, obj, context, path):
        raw_seconds = Int16ub.parse(obj)
        return timedelta(seconds=raw_seconds)
    def _encode(self, obj, context, path):
        raise NotImplementedError()
SportidentTime = SportidentTimeAdapter(Bytes(2))

class SportidentCardAdapter(Adapter):
    def _decode(self, obj, context, path):
        buf = bytes(obj[0:4])
        if buf[0] == 0x00:
            # Try decoding as SI-Card 5
            prefix = buf[1]
            remainder = int.from_bytes(buf[2:4], 'big')
            sicard5_number = prefix * 100000 + remainder
            if 100000 < sicard5_number < 500000 and 1 <= prefix <= 9:
                return sicard5_number
            else:
                return int.from_bytes(buf[1:4], 'big')
        elif 1 <= buf[0] <= 9:
            nr = int.from_bytes(buf[1:3], 'big')
            return buf[0] * 100000 + nr
        else:
            return int.from_bytes(buf[0:3], 'big')
    def _encode(self, obj, context, path):
        raise NotImplementedError()
SportidentCard = SportidentCardAdapter(Bytes(4))

SiPacket = Struct(
    "Wakeup"  / Optional(Const(b"\xFF")),
    "Stx"     / Const(b"\x02"),
    "Command" / Const(b"\xD3"),
    "Len"     / Int8ub,       # Dovrebbe essere 13
    "Cn"      / Int16ub,      # Station number (control)
    "SiNr"    / SportidentCard, # SI card number (chip number)
    "Td"      / Int8ub,       # Byte TD: informazioni sul tempo
    "ThTl"    / SportidentTime, # 2 byte: timer in secondi
    "Tsubsec" / Int8ub,       # 1 byte: sottosecondi
    "Mem"     / Int24ub,      # Flag/offset (3 byte)
    "Crc1"    / Int8ub,       # CRC high byte (ignorato)
    "Crc2"    / Int8ub,       # CRC low byte (ignorato)
    "Etx"     / Const(b"\x03")
)

# --------------------------
# Funzione per il calcolo del tempo
# --------------------------
def convert_extended_time(td_byte: int, th_tl_bytes: bytes, tss_byte: int):
    half_day_flag = td_byte & 0x01
    t12 = int.from_bytes(th_tl_bytes, 'big')
    if half_day_flag == 1:
        t12 += 12 * 3600
    fractional = tss_byte / 256.0
    total_seconds = t12 + fractional
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
    return {
        'time_of_day_seconds': total_seconds,
        'formatted_time': formatted_time
    }

# --------------------------
# Funzione per l'estrazione del frame basata sul campo LEN
# --------------------------
def extract_frame(buffer: bytearray) -> (bytes, bytearray):
    """
    Estrae un frame dal buffer basandosi sul campo LEN.
    
    Struttura attesa (escludendo eventuali byte di wakeup 0xFF):
      - 0x02 (STX)
      - Command (1 byte)
      - LEN (1 byte): lunghezza del payload, esclusi i 2 byte CRC
      - Payload (LEN byte)
      - CRC1 (1 byte)
      - CRC2 (1 byte)
      - 0x03 (ETX)
    
    Lunghezza totale = LEN + 6.
    """
    while buffer and buffer[0] == 0xFF:
        buffer.pop(0)
    
    try:
        start = buffer.index(0x02)
    except ValueError:
        return None, buffer
    
    if len(buffer) - start < 3:
        return None, buffer
    
    length = buffer[start + 2]
    frame_total_length = length + 6
    if len(buffer) - start < frame_total_length:
        return None, buffer
    
    frame = bytes(buffer[start:start+frame_total_length])
    new_buffer = buffer[start+frame_total_length:]
    
    if frame[-1] != 0x03:
        logging.error("Frame terminato in modo errato: atteso 0x03, ottenuto %s", hex(frame[-1]))
        return None, new_buffer
    
    return frame, new_buffer

# --------------------------
# Funzione per il lenient parsing del payload D3
# --------------------------
def parse_d3_payload_lenient(data: bytes):
    if len(data) < 6:
        logging.error(f"Payload troppo corto per station e card: attesi almeno 6 byte, ottenuti {len(data)}")
        return None

    control = int.from_bytes(data[0:2], 'big')
    card_bytes = data[2:6]
    if card_bytes[0] == 0x00:
        prefix = card_bytes[1]
        remainder = int.from_bytes(card_bytes[2:4], 'big')
        sicard5_number = prefix * 100000 + remainder
        if 100000 < sicard5_number < 500000 and 1 <= prefix <= 9:
            card_number = sicard5_number
        else:
            card_number = int.from_bytes(card_bytes[1:4], 'big')
    elif 1 <= card_bytes[0] <= 9:
        prefix = card_bytes[0]
        remainder = int.from_bytes(card_bytes[1:3], 'big')
        card_number = prefix * 100000 + remainder
    else:
        card_number = int.from_bytes(card_bytes[0:3], 'big')

    logging.warning(f"Payload D3 inatteso: lunghezza {len(data)} invece di 13 (trovati {len(data)}). Parsing leniently.")

    punch_time_str = "Tempo non disponibile (payload incompleto)"
    if len(data) >= 10:
        td = data[6]
        th_tl = int.from_bytes(data[7:9], 'big')
        tsubsec = data[9]
        time_info = convert_extended_time(td, th_tl.to_bytes(2, 'big'), tsubsec)
        today_midnight = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        punch_time_dt = today_midnight + timedelta(seconds=time_info['time_of_day_seconds'])
        punch_time_str = punch_time_dt.strftime('%Y-%m-%d %H:%M:%S.%f')
        logging.info(f"Orario decodificato (lenient): {punch_time_str}")

    return {
        'control': control,
        'card_number': card_number,
        'punch_time': punch_time_str,
        'day_offset': "Offset non disponibile (payload incompleto)",
        'time_info': {}
    }

# --------------------------
# Funzione per decodificare il pacchetto Sportident
# --------------------------
def decode_sportident(raw_data: bytes):
    original_raw = raw_data.hex()
    if raw_data and raw_data[0] == 0xFF:
        raw_data = raw_data[1:]
    if not (raw_data.startswith(b'\x02') and raw_data.endswith(b'\x03')):
        logging.error(f"Framing non valido: {raw_data.hex()}")
        return None
    payload_plus_crc = raw_data[1:-1]
    payload_plus_crc = remove_dle(payload_plus_crc)
    if not payload_plus_crc:
        logging.error("Payload vuoto dopo DLE")
        return None
    CMD = payload_plus_crc[0]
    decoded = {'CMD': CMD, 'raw_punch_data': original_raw}
    if CMD >= 0x80 and CMD != 0xC4:
        if len(payload_plus_crc) < 2:
            logging.error("Messaggio troppo corto per LEN")
            return None
        LEN_byte = payload_plus_crc[1]
        decoded['LEN'] = LEN_byte
        data = payload_plus_crc[2:2+LEN_byte]
        if CMD == 0xD3 and LEN_byte == 0x0D:
            punch_info = parse_d3_payload_lenient(data)
            if punch_info:
                decoded.update(punch_info)
                print(f"Station (Control): {punch_info['control']}")
                print(f"Chip number: {punch_info['card_number']}")
                print(f"Punch time: {punch_info['punch_time']}")
                print("-" * 20)
                return decoded
            else:
                return None
        else:
            decoded['DATA'] = data.hex()
            return decoded
    else:
        data = payload_plus_crc[1:]
        decoded['DATA'] = data.hex()
        decoded['crc_valid'] = True
        return decoded

# --------------------------
# Funzione per preparare i dati per il DB
# --------------------------
def parse_packet_for_db(packet):
    parsed = {
        'cmd': int(packet['CMD']),
        'len': packet['LEN'],
        'control': packet.get('control'),
        'card_number': packet.get('card_number'),
        'punch_time': packet.get('punch_time'),
        'raw_punch_data': packet['raw_punch_data'],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    return parsed

# --------------------------
# Funzioni per il database
# --------------------------
def get_db_connection():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        logging.error("Errore di connessione al DB: %s", err)
        return None

def insert_into_db(parsed):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    INSERT INTO radiocontrol (
        control, card_number, punch_time, raw_punch_data, timestamp, sent_internet
    ) VALUES (%s, %s, %s, %s, %s, %s)
    """
    values = (
        parsed.get('control'),
        parsed.get('card_number'),
        parsed.get('punch_time'),
        parsed['raw_punch_data'],
        parsed['timestamp'],
        0  # Imposta sent_internet a 0 di default
    )
    last_insert_id = None
    try:
        with threading.Lock():
            cursor.execute(query, values)
            conn.commit()
            last_insert_id = cursor.lastrowid
        logging.info("Inserimento DB completato in radiocontrol per: %s - Chip number: %s",
                     parsed['raw_punch_data'], parsed['card_number'])
    except Exception as e:
        logging.error("Errore nell'inserimento DB in radiocontrol: %s", e)
    finally:
        cursor.close()
        if conn and conn.is_connected():
            conn.close()
    return last_insert_id

def fetch_record_by_id(record_id):
    """Recupera un record dalla tabella radiocontrol in base al suo ID."""
    conn = get_db_connection()
    if not conn:
        logging.error("Connessione al DB non riuscita per record_id: %s", record_id)
        return None
    try:
        with conn.cursor(dictionary=True) as cursor:
            query = "SELECT * FROM radiocontrol WHERE id = %s"
            cursor.execute(query, (record_id,))
            record = cursor.fetchone()
            if record is None:
                logging.warning("Nessun record trovato per id %s", record_id)
            return record
    except mysql.connector.Error as err:
        logging.error("Errore in fetch_record_by_id per id %s: %s", record_id, err)
        return None
    finally:
        conn.close()

def get_device_identifiers():
    """
    Recupera i valori 'nome' e 'pkey' dalla tabella costanti.
    Restituisce (nome, pkey) oppure (None, None) in caso di errore.
    """
    conn = get_db_connection()
    if not conn:
        return None, None
    try:
        cursor = conn.cursor()
        query = "SELECT nome, valore FROM costanti WHERE nome IN ('nome', 'pkey') ORDER BY nome"
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        if len(results) == 2:
            identifiers = {row[0]: row[1] for row in results}
            return identifiers.get('nome'), identifiers.get('pkey')
        else:
            logging.error("Campi 'nome' e 'pkey' non trovati nella tabella costanti.")
            return None, None
    except mysql.connector.Error as err:
        logging.error("Errore in get_device_identifiers: %s", err)
        return None, None

def log_event(nome, errore, descrizione):
    """Scrive un evento nella tabella 'log'."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        query = "INSERT INTO log (nome, errore, descrizione) VALUES (%s, %s, %s)"
        cursor.execute(query, (nome, errore, descrizione))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except mysql.connector.Error as err:
        logging.error("Errore durante la scrittura nel log: %s", err)
        return False

def send_record_online(record):
    record_id = record.get('id')
    device_name, device_pkey = get_device_identifiers()
    if not device_name or not device_pkey:
        logging.error("Impossibile recuperare device identifiers per record %s.", record_id)
        return

    record_to_send = record.copy()
    record_to_send['name'] = device_name
    record_to_send['pkey'] = device_pkey

    if isinstance(record_to_send.get('punch_time'), datetime):
        record_to_send['punch_time'] = record_to_send['punch_time'].isoformat()
    if isinstance(record_to_send.get('timestamp'), datetime):
        record_to_send['timestamp'] = record_to_send['timestamp'].isoformat()

    try:
        # Riduci il timeout se il server risponde velocemente (ad esempio, 5 secondi)
        response = requests.post(REMOTE_URL, json=record_to_send, timeout=5)
        sys.stdout.flush()
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("status") == "success":
                    print(f"Inviato online: id={record['id']}, control={record['control']}, number={record['card_number']}, time={record['punch_time']}")
                    logging.info(f"Record {record_id} inviato correttamente online.")
                    log_event(device_name, "Successo", f"Punzonatura inviata online - id={record['id']}, control={record['control']}, number={record['card_number']}, time={record['punch_time']}")
                else:
                    logging.error(f"Errore invio record {record_id}: {data}")
                    log_event(device_name, "Errore Invio", f"Errore durante l'invio del record {record_id} online: {data}")
            except ValueError as e:
                logging.error(f"Errore parsing JSON per record {record_id}: {str(e)}")
                log_event(device_name, "Errore JSON", f"Errore durante l'analisi della risposta JSON per il record {record_id}: {str(e)}")
        else:
            logging.error(f"HTTP {response.status_code} per record {record_id}. Risposta: {response.text}")
            log_event(device_name, f"Errore HTTP {response.status_code}", f"Errore HTTP durante l'invio del record {record_id}. Risposta: {response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Errore di connessione per record {record_id}: {e}")
        log_event(device_name, "Errore Connessione", f"Errore di connessione durante l'invio del record {record_id}: {e}")
    except Exception as e:
        logging.error(f"ERRORE INASPETTATO durante l'invio del record {record_id}: {e}")
        log_event(device_name, "Errore Inatteso", f"Errore inatteso durante l'invio del record {record_id}: {e}")

def process_and_send_punch(record_id):
    """Recupera un record dal DB e lo invia online."""
    record = fetch_record_by_id(record_id)
    if record:
        send_record_online(record)

# --------------------------
# Loop di lettura dalla porta seriale
# --------------------------
try:
    ser = serial.Serial(port='/dev/ttyUSB0', baudrate=38400, timeout=0.1)
    logging.info("Porta seriale aperta: %s a %d baud", ser.portstr, ser.baudrate)
except Exception as e:
    logging.critical("Errore nell'apertura della porta seriale: %s", e)
    exit(1)

recv_buffer = bytearray()
# Aumenta il numero di worker per gestire più richieste in parallelo
executor = ThreadPoolExecutor(max_workers=10)
logging.info("Inizio lettura dati dalla porta seriale...")

while True:
    try:
        data = ser.read(200)
        if data:
            logging.debug("Dati grezzi ricevuti: %s", data.hex())
            recv_buffer.extend(data)
            while True:
                frame, recv_buffer = extract_frame(recv_buffer)
                if frame is None:
                    break
                try:
                    packet = decode_sportident(frame)
                    if packet:
                        parsed_data = parse_packet_for_db(packet)
                        last_id = insert_into_db(parsed_data)
                        if last_id:
                            logging.info(f"Record inserito con last_id: {last_id}")
                            executor.submit(process_and_send_punch, last_id)
                        else:
                            logging.error("Errore: ID non ottenuto dopo l'inserimento nel DB.")
                    else:
                        logging.error("Pacchetto non decodificato correttamente.")
                except Exception as parse_err:
                    logging.error("Errore nel parsing del pacchetto: %s", parse_err)
        else:
            time.sleep(0.01)
    except Exception as e:
        logging.exception("Errore durante la lettura dalla porta seriale: %s", e)

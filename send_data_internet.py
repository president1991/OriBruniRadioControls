#!/usr/bin/env python3
"""
Servizio che controlla la tabella 'radiocontrol' nel database locale e,
per ogni record non ancora inviato online (sent_internet = 0), lo invia
in modo asincrono al server remoto. Al record viene aggiunto, nel payload,
il campo 'name' e 'pkey' recuperati dalla tabella 'costanti', per identificare
da quale radiocontrol provenga la punzonatura.
In caso di successo (risposta JSON con "status": "success"), il record
viene aggiornato (sent_internet impostato a 1) e viene scritto un log.
In caso di errore, viene scritto un log.
"""

import mysql.connector
import requests
import time
import logging
import sys
import datetime
from concurrent.futures import ThreadPoolExecutor

# Configurazione del logging (INFO per output essenziale)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configurazione del database locale
db_config = {
    'user': 'root',
    'password': 'PuhA7gWCrW',
    'host': 'localhost',
    'database': 'OriBruniRadioControls'
}

# URL del servizio remoto
REMOTE_URL = "https://orienteering.services/radiocontrol/receive_data.php"

def get_db_connection():
    try:
        return mysql.connector.connect(**db_config)
    except mysql.connector.Error as err:
        logging.error("Errore di connessione al DB: %s", err)
        return None

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

def fetch_unsent_records():
    """Recupera tutti i record con sent_internet = 0 dalla tabella radiocontrol."""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM radiocontrol WHERE sent_internet = 0"
        cursor.execute(query)
        records = cursor.fetchall()
        cursor.close()
        conn.close()
        return records
    except mysql.connector.Error as err:
        logging.error("Errore in fetch_unsent_records: %s", err)
        return

def mark_record_as_sent(record_id):
    """Aggiorna il record impostando sent_internet a 1."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        query = "UPDATE radiocontrol SET sent_internet = 1 WHERE id = %s"
        cursor.execute(query, (record_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except mysql.connector.Error as err:
        logging.error("Errore in mark_record_as_sent per record %s: %s", record_id, err)
        return False

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

    # print(f"Inizio invio per record: {record_id}")

    record_to_send = record.copy()
    record_to_send['name'] = device_name
    record_to_send['pkey'] = device_pkey

    # Converti gli oggetti datetime in stringhe ISO 8601
    if isinstance(record_to_send.get('punch_time'), datetime.datetime):
        record_to_send['punch_time'] = record_to_send['punch_time'].isoformat()
    if isinstance(record_to_send.get('timestamp'), datetime.datetime):
        record_to_send['timestamp'] = record_to_send['timestamp'].isoformat()

    # print(f"Payload da inviare: {record_to_send}")
    # print(f"URL di destinazione: {REMOTE_URL}")

    try:
        response = requests.post(REMOTE_URL, json=record_to_send, timeout=10)
        # print(f"Codice di stato HTTP per record {record_id}: {response.status_code}")
        # print(f"Response JSON per record {record_id}: {response.text}")
        sys.stdout.flush()
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("status") == "success":
                    print(f"Inviato: id={record['id']}, control={record['control']}, number={record['card_number']}, time={record['punch_time']}")
                    logging.info(f"Record {record_id} inviato correttamente.")
                    log_event(device_name, "Successo", f"Punzonatura inviata online - id={record['id']}, control={record['control']}, number={record['card_number']}, time={record['punch_time']}")
                    if not mark_record_as_sent(record_id):
                        logging.error(f"Errore aggiornamento record {record_id}.")
                        log_event(device_name, "Errore DB", f"Errore durante l'aggiornamento del record {record_id} come inviato.")
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

def main_service_loop():
    executor = ThreadPoolExecutor(max_workers=4)
    logging.info("Avvio servizio di invio dati online.")
    while True:
        records = fetch_unsent_records()
        if records:
            logging.info("Trovati %d record non inviati.", len(records))
            for record in records:
                executor.submit(send_record_online, record)
        else:
            logging.info("Nessun record da inviare.")
        time.sleep(60)

if __name__ == "__main__":
    main_service_loop()
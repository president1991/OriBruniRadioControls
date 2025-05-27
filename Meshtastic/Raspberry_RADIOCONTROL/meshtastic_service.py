#!/usr/bin/env python3
# meshtastic_service.py

import time
import threading
import logging
import json
import glob
import configparser
import os
import fcntl
import signal
import mysql.connector
from mysql.connector import pooling
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from enum import IntEnum
from meshtastic.serial_interface import SerialInterface

# Configura il logger di root prima di qualsiasi operazione
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# --- Caricamento config ---
cfg = configparser.ConfigParser()
cfg.read('config.ini')

# --- Pool di connessioni MySQL ---
dbconfig = {
    'host':     cfg['DATABASE']['host'],
    'user':     cfg['DATABASE']['user'],
    'password': cfg['DATABASE']['password'],
    'database': cfg['DATABASE']['database'],
    'raise_on_warnings': True,
}
db_pool = pooling.MySQLConnectionPool(
    pool_name = "meshtastic_pool",
    pool_size = 2,
    **dbconfig
)

# --- Enumerazione tipi di messaggio ---
class MessageType(IntEnum):
    TELEMETRY = 0
    PUNCHES   = 1

def log_to_db(direction: str, msg_type: int, payload: str, peer_id: str = ''):
    """
    Inserisce una riga nella tabella meshtastic_log.
    """
    global node_name  # Dichiarazione esplicita che stiamo usando la variabile globale
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor()
        # Stampo un log dettagliato per debug
        current_node_name = node_name or 'unknown_node'
        logging.info(f"[mesh][DB] Scrivo log: {direction}, tipo {msg_type}, node {current_node_name}, peer {peer_id}")
        
        sql = """
            INSERT INTO meshtastic_log
              (direction, msg_type, event_time, node_name, peer_id, payload)
            VALUES
              (%s,         %s,       NOW(),      %s,        %s,      %s)
        """
        cursor.execute(sql, (
            direction,
            msg_type,
            current_node_name,
            peer_id,
            payload
        ))
        conn.commit()
        # Log di successo per debugging
        logging.info(f"[mesh][DB] Log scritto con successo, ID={cursor.lastrowid}")
    except Exception as e:
        logging.error(f"[mesh][DB] Errore log_to_db: {e}")
        # Log più dettagliato per debugging
        logging.error(f"[mesh][DB] Dettagli: direction={direction}, type={msg_type}, node={node_name}, peer={peer_id}")
        try:
            # Tentativo di eseguire una query semplice per verificare la connessione DB
            test_conn = db_pool.get_connection()
            test_cursor = test_conn.cursor()
            test_cursor.execute("SELECT 1")
            test_cursor.fetchone()
            logging.info("[mesh][DB] Test connessione DB: OK")
            test_cursor.execute("SHOW TABLES LIKE 'meshtastic_log'")
            table_exists = len(test_cursor.fetchall()) > 0
            logging.info(f"[mesh][DB] Tabella meshtastic_log esiste: {table_exists}")
            if table_exists:
                test_cursor.execute("DESCRIBE meshtastic_log")
                columns = [row[0] for row in test_cursor.fetchall()]
                logging.info(f"[mesh][DB] Colonne tabella: {columns}")
            test_cursor.close()
            test_conn.close()
        except Exception as db_test_err:
            logging.error(f"[mesh][DB] Test DB fallito: {db_test_err}")
    finally:
        try:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'conn' in locals() and conn:
                conn.close()
        except Exception as close_err:
            logging.error(f"[mesh][DB] Errore chiusura connessione: {close_err}")

# --- Ricerca della porta Meshtastic via symlink by-id ---
meshtastic_port = None
for path in glob.glob('/dev/serial/by-id/*'):
    if 'CP2102' in path or 'Meshtastic' in path:
        meshtastic_port = path
        break

if meshtastic_port:
    cfg.set('MESHTASTIC', 'PORT', meshtastic_port)
    logging.info(f"[mesh] Porta Meshtastic rilevata: {meshtastic_port}")
else:
    logging.critical("Nessuna porta Meshtastic trovata su /dev/serial/by-id")
    try:
        log_db_error(
            'Errore Porta Meshtastic Non Trovata',
            'Nessun dispositivo CP2102 rilevato',
            cfg
        )
    except NameError:
        pass
    raise RuntimeError("Nessuna porta Meshtastic trovata.")

logging.info(f"[mesh] Uso MESH_PORT = {meshtastic_port}")

# Lettura delle altre impostazioni
NEIGH_INTERVAL = cfg.getint('MESHTASTIC', 'NEIGH_INFO_INTERVAL')
HTTP_PORT     = cfg.getint('MESHTASTIC', 'HTTP_PORT', fallback=8000)
MESH_PORT     = cfg['MESHTASTIC']['PORT']
logging.info(f"[mesh] NEIGH_INFO_INTERVAL = {NEIGH_INTERVAL}s, HTTP_PORT = {HTTP_PORT}")

# Stato globale
mesh: SerialInterface = None
neighbors = {}
node_name = None
node_pkey = None

# Funzione per leggere nome e pkey del nodo dal DB
def get_node_credentials():
    db_conf = {
        'host': cfg['DATABASE']['host'],
        'user': cfg['DATABASE']['user'],
        'password': cfg['DATABASE']['password'],
        'database': cfg['DATABASE']['database']
    }
    try:
        conn = mysql.connector.connect(**db_conf)
        cursor = conn.cursor()
        cursor.execute("SELECT nome, valore FROM costanti WHERE nome IN ('nome','pkey')")
        rows = cursor.fetchall()
        creds = {row[0]: row[1] for row in rows}
        return creds.get('nome'), creds.get('pkey')
    except Exception as e:
        logging.error(f"[mesh] Errore lettura credenziali nodo: {e}")
        return None, None
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

# Modello per i payload in ingresso
class Payload(BaseModel):
    type: str
    timestamp: float
    data: dict

# FastAPI app
app = FastAPI()

# Gestione pacchetti ricevuti dalla mesh
def on_receive(pkt, interface):
    peer = pkt.get('from')
    if peer is None:
        return
    neighbors[peer] = {
        'rssi': pkt.get('rssi'),
        'snr': pkt.get('snr'),
        'seen': time.time()
    }
    raw = pkt.get('decoded', pkt)
    text = raw.get('payload') or raw.get('text') or str(pkt)
    logging.info(f"[mesh] pacchetto ricevuto da {peer}: {text}")

    # Log su DB
    try:
        mt = int(text.split(";", 1)[0])
    except:
        mt = -1
    log_to_db(
        direction="receive",
        msg_type=mt,
        payload=text,
        peer_id=str(peer)
    )

# Invia telemetria periodicamente
def send_telemetry():
    if mesh is None:
        return
    parts = [
        str(MessageType.TELEMETRY.value),
        str(time.time()),
        node_name or '',
        node_pkey or ''
    ]
    for nid, vals in neighbors.items():
        parts.append(f"{nid},{vals['rssi']},{vals['snr']},{vals['seen']}")
    payload = ";".join(parts)

    try:
        mesh.sendText(payload)
        logging.info(f"[mesh] telemetria inviata: {len(neighbors)} vicini")
        log_to_db(
            direction="send",
            msg_type=MessageType.TELEMETRY.value,
            payload=payload,
            peer_id=''
        )
    except Exception as ex:
        logging.error(f"[mesh] errore invio telemetria: {ex}")
        log_to_db(
            direction="send",
            msg_type=MessageType.TELEMETRY.value,
            payload=f"ERROR:{ex}|{payload}",
            peer_id=''
        )

# Thread di telemetria
def telemetry_loop():
    while True:
        send_telemetry()
        time.sleep(NEIGH_INTERVAL)

# Evento di avvio del servizio
@app.on_event("startup")
def startup():
    global mesh, node_name, node_pkey
    node_name, node_pkey = get_node_credentials()
    logging.info(f"[mesh] Nodo: {node_name}, pkey: {node_pkey}")
    try:
        fd = os.open(MESH_PORT, os.O_RDONLY | os.O_NONBLOCK)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
    except BlockingIOError:
        logging.error(f"[mesh] Porta {MESH_PORT} già in uso da un altro processo (pre-check)")
        raise RuntimeError(f"Porta {MESH_PORT} già in uso. Chiudi altri programmi e riprova.")
    logging.info("[mesh] Porta libera, procedo con apertura serial interface")
    max_retries = 5
    retry_delay = 2  # secondi
    for attempt in range(1, max_retries + 1):
        try:
            mesh = SerialInterface(devPath=MESH_PORT)
            if hasattr(mesh, 'onReceive'):
                mesh.onReceive(on_receive)
            else:
                logging.warning(f"[mesh] Metodo onReceive non disponibile, callback non registrata")
            logging.info(f"[mesh] Porta seriale aperta su {MESH_PORT}")
            break
        except Exception as ex:
            logging.error(f"[mesh] Tentativo {attempt}/{max_retries} fallito: {ex}")
            if attempt == max_retries:
                logging.critical(f"[mesh] Impossibile aprire la porta dopo {max_retries} tentativi, esco.")
                raise
            time.sleep(retry_delay)
    logging.info(f"[mesh] Service avviato; telemetria ogni {NEIGH_INTERVAL}s")
    threading.Thread(target=telemetry_loop, daemon=True).start()

# Evento di arresto del servizio
@app.on_event("shutdown")
def shutdown_event():
    logging.info("[mesh] Chiusura serial interface in shutdown event")
    if mesh:
        mesh.close()


@app.post("/send_raw")
def send_raw(payload: str = Body(..., media_type="text/plain")):
    """
    Riceve un payload testuale 'tipo;campo1;campo2;…' e lo manda in mesh + DB.
    """
    # Invia sulla mesh
    mesh.sendText(payload)
    # Estrai msg_type dal primo campo
    try:
        mt = int(payload.split(";", 1)[0])
    except:
        mt = -1
    # Log su DB
    log_to_db(
        direction="send",
        msg_type=mt,
        payload=payload,
        peer_id=""
    )
    return {"status": "sent"}

# Endpoint HTTP per invio payload generici
@app.post("/send_payload")
def send_payload(payload: Payload):
    """Endpoint per inviare un payload JSON generico sulla mesh."""
    try:
        body = json.dumps(payload.dict())
        logging.info(f"[mesh] invio payload HTTP: {body}")
        mesh.sendText(body)
        # Log su DB
        log_to_db(
            direction="send",
            msg_type=-1,
            payload=body,
            peer_id=''
        )
        return {"status": "sent"}
    except Exception as e:
        logging.error(f"[mesh] Errore invio payload: {e}, payload: {payload.json()}")
        raise HTTPException(status_code=500, detail=str(e))

# Avvio dell'applicazione
if __name__ == "__main__":
    def _shutdown_handler(sig, frame):
        logging.info(f"[mesh] Ricevuto segnale {sig}, chiusura serial interface")
        if mesh:
            mesh.close()
        exit(0)

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    try:
        logging.info(f"[mesh] Avvio Uvicorn su porta {HTTP_PORT}")
        import uvicorn
        uvicorn.run(
            "meshtastic_service:app",
            host="0.0.0.0",
            port=HTTP_PORT,
            log_level="info"
        )
    finally:
        logging.info("[mesh] Chiusura serial interface in main finally")
        if mesh:
            mesh.close()

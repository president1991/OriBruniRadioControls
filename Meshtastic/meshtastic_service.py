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
import mysql.connector  # Added to read node credentials from DB
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
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

# Nel caso servisse, mostra anche il valore in uso
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
    # Log completa del pacchetto ricevuto
    logging.info(f"[mesh] pacchetto ricevuto da {peer}: {json.dumps(pkt)}")

# Invia telemetria periodicamente
def send_telemetry():
    if mesh is None:
        return
    payload = {
        'type': 'neigh_info',
        'timestamp': time.time(),
        'name': node_name,
        'pkey': node_pkey,
        'data': [
            {'id': nid, **vals}
            for nid, vals in neighbors.items()
        ]
    }
    try:
        mesh.sendText(json.dumps(payload))
        logging.info(f"[mesh] telemetria inviata ({len(neighbors)} vicini) nodo={node_name}")
        # Log dettagliato del payload di telemetria
        logging.debug(f"[mesh] telemetria payload: {json.dumps(payload)}")
    except Exception as ex:
        logging.error(f"[mesh] errore invio telemetria: {ex}, payload: {json.dumps(payload)}")

# Thread di telemetria
def telemetry_loop():
    while True:
        send_telemetry()
        time.sleep(NEIGH_INTERVAL)

# Evento di avvio del servizio
@app.on_event("startup")
def startup():
    global mesh, node_name, node_pkey
    # Leggi credenziali nodo dal DB
    node_name, node_pkey = get_node_credentials()
    logging.info(f"[mesh] Nodo: {node_name}, pkey: {node_pkey}")
    # Controllo preliminare se la porta è già aperta da un altro processo
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

# Endpoint HTTP per invio payload generici
@app.post("/send_payload")
def send_payload(payload: Payload):
    """Endpoint per inviare un payload JSON generico sulla mesh."""
    try:
        # Log del payload in invio
        logging.info(f"[mesh] invio payload HTTP: {payload.json()}")
        mesh.sendText(json.dumps(payload.dict()))
        return {"status": "sent"}
    except Exception as e:
        logging.error(f"[mesh] Errore invio payload: {e}, payload: {payload.json()}")
        raise HTTPException(status_code=500, detail=str(e))

# Avvio dell'applicazione
if __name__ == "__main__":
    # Handler per segnali di terminazione
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
        # Chiusura seriale al termine
        logging.info("[mesh] Chiusura serial interface in main finally")
        if mesh:
            mesh.close()

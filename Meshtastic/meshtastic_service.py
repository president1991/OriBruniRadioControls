#!/usr/bin/env python3
# meshtastic_service.py

import time
import threading
import logging
import json
import configparser
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from meshtastic.serial_interface import SerialInterface

# --- Caricamento config ---
cfg = configparser.ConfigParser()
cfg.read('config.ini')
MESH_PORT       = cfg['MESHTASTIC']['PORT']
NEIGH_INTERVAL  = cfg.getint('MESHTASTIC', 'NEIGH_INFO_INTERVAL')
HTTP_PORT       = cfg.getint('MESHTASTIC', 'HTTP_PORT')  # aggiungi in config

# --- Stato globale ---
mesh: SerialInterface
neighbors = {}

# --- Modello per i payload in ingresso ---
class Payload(BaseModel):
    type: str
    timestamp: float
    data: dict

# --- FastAPI app ---
app = FastAPI()

def on_receive(pkt, interface):
    peer = pkt.get('from')
    if peer is None:
        return
    neighbors[peer] = {
        'rssi': pkt.get('rssi'),
        'snr': pkt.get('snr'),
        'seen': time.time()
    }
    logging.debug(f"[mesh] ricevuto da {peer}: RSSI={neighbors[peer]['rssi']}")

def send_telemetry():
    payload = {
        'type': 'neigh_info',
        'timestamp': time.time(),
        'data': [
            {'id': nid, **vals}
            for nid, vals in neighbors.items()
        ]
    }
    try:
        mesh.sendText(json.dumps(payload))
        logging.info(f"[mesh] telemetria inviata ({len(neighbors)} vicini)")
    except Exception as ex:
        logging.error(f"[mesh] errore invio telemetria: {ex}")

def telemetry_loop():
    while True:
        send_telemetry()
        time.sleep(NEIGH_INTERVAL)

@app.on_event("startup")
def startup():
    global mesh
    logging.basicConfig(level=logging.INFO)
    mesh = SerialInterface(devPath=MESH_PORT)
    mesh.onReceive(on_receive)
    logging.info(f"[mesh] Service avviato su {MESH_PORT}; telemetria ogni {NEIGH_INTERVAL}s")
    # avvia thread di telemetria periodica
    threading.Thread(target=telemetry_loop, daemon=True).start()

@app.on_event("shutdown")
def shutdown():
    mesh.close()

@app.post("/send_payload")
def send_payload(payload: Payload):
    """Endpoint per inviare un payload JSON generico sulla mesh."""
    try:
        mesh.sendText(json.dumps(payload.dict()))
        return {"status": "sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# versione 1.3
# 22/04/2025

import mysql.connector
import requests
import time

# Configurazione DB
db_config = {
    'user': 'root',
    'password': 'PuhA7gWCrW',
    'host': 'localhost',
    'database': 'OriBruniRadioControls',
    'autocommit': True
}

# URL call‑home
url = "https://orienteering.services/radiocontrol/callhome.php"

# Intervallo di polling (in secondi)
POLL_INTERVAL = 5

def crea_connessione_db():
    return mysql.connector.connect(**db_config)

def leggi_dati(cursor):
    cursor.execute("""
        SELECT nome, valore
        FROM costanti
        WHERE nome IN ('nome', 'pkey')
        ORDER BY nome
    """)
    risultati = cursor.fetchall()
    if len(risultati) == 2:
        vals = {r[0]: r[1] for r in risultati}
        return vals['nome'], vals['pkey']
    else:
        print("[WARN] costanti incomplete")
        return None, None

def invia_callhome(session, nome, pkey):
    params = {"name": nome, "pkey": pkey}
    try:
        # Prima proviamo HEAD (niente body)
        resp = session.head(url, params=params, timeout=5)
        if resp.status_code == 405:  # metodo non consentito
            # fallback a GET (gzip già abilitato)
            resp = session.get(url, params=params, timeout=5)
        resp.raise_for_status()
        print(f"[OK] dispositivo online: {time.strftime('%H:%M:%S')}")
    except requests.RequestException as e:
        print(f"[ERR] callhome: {e}")

def main_loop():
    conn = crea_connessione_db()
    cursor = conn.cursor()
    session = requests.Session()
    session.headers.update({
        "User-Agent": "OriBruniClient/1.3",
        "Accept-Encoding": "gzip",
        "Connection": "keep-alive"
    })

    while True:
        nome, pkey = leggi_dati(cursor)
        if nome and pkey:
            invia_callhome(session, nome, pkey)
        else:
            print("[ERR] dati mancanti, skip callhome")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main_loop()

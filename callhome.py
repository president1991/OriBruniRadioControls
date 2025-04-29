#!/usr/bin/env python3
"""
callhome.py v2.0
Invia periodicamente un POST JSON a callhome.php con keepalive e metriche di sistema.
"""
import mysql.connector
import requests
import time
import psutil
import json
from datetime import datetime

# Configurazione DB
db_config = {
    'user': 'root',
    'password': 'PuhA7gWCrW',
    'host': 'localhost',
    'database': 'OriBruniRadioControls',
    'autocommit': True
}

# Endpoint keepalive
url = "https://orienteering.services/radiocontrol/callhome.php"

# Intervallo di polling in secondi 
POLL_INTERVAL = 5


def crea_connessione_db():
    try:
        print(f"[INFO] Connessione al database {db_config['database']}...")
        conn = mysql.connector.connect(**db_config)
        print(f"[OK] Connessione al database stabilita")
        return conn
    except mysql.connector.Error as err:
        print(f"[ERR] Errore connessione DB: {err}")
        return None


def leggi_credentials(cursor):
    """Recupera nome e pkey dalla tabella costanti"""
    try:
        print("[INFO] Lettura credenziali dalla tabella costanti...")
        cursor.execute("""
            SELECT nome, valore
            FROM costanti
            WHERE nome IN ('nome', 'pkey')
            ORDER BY nome
        """)
        risultati = cursor.fetchall()
        if len(risultati) == 2:
            vals = {r[0]: r[1] for r in risultati}
            nome = vals['nome']
            pkey = vals['pkey']
            print(f"[OK] Credenziali trovate - nome: {nome}, pkey: {pkey[:5]}***")
            return nome, pkey
        else:
            trovati = [r[0] for r in risultati] if risultati else []
            print(f"[WARN] Costanti incomplete - trovate: {trovati}, mancanti: {'nome' if 'nome' not in trovati else ''} {'pkey' if 'pkey' not in trovati else ''}")
            return None, None
    except mysql.connector.Error as err:
        print(f"[ERR] Errore lettura credenziali: {err}")
        return None, None


def check_system_health():
    """Raccoglie metriche di sistema"""
    print("[INFO] Raccolta metriche di sistema...")
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    temp = None
    # Prova a leggere temperatura su Raspberry Pi
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read()) / 1000.0
    except Exception as e:
        print(f"[WARN] Impossibile leggere temperatura: {e}")
    
    metrics = {
        'cpu_percent': cpu,
        'memory_percent': mem,
        'disk_percent': disk,
        'temperature': temp
    }
    print(f"[INFO] Metriche: CPU {cpu}%, MEM {mem}%, DISK {disk}%, TEMP {temp if temp else 'N/A'}")
    return metrics


def invia_keepalive(session, nome, pkey):
    """Invia POST JSON con keepalive e metriche al server"""
    print(f"\n[INFO] Preparazione keepalive per dispositivo '{nome}'...")
    system_metrics = check_system_health()
    
    payload = {
        'name': nome,
        'pkey': pkey,
        'action': 'keepalive',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'system_status': system_metrics
    }
    
    print(f"[INFO] Invio keepalive a {url}...")
    print(f"[DEBUG] Payload: {json.dumps({k: v if k != 'pkey' else '***' for k, v in payload.items()}, indent=2)}")
    
    try:
        start_time = time.time()
        resp = session.post(url, json=payload, timeout=10)
        elapsed = time.time() - start_time
        
        print(f"[INFO] Risposta ricevuta in {elapsed:.2f}s - Status: {resp.status_code}")
        
        resp.raise_for_status()
        try:
            data = resp.json()
            print(f"[DEBUG] Risposta JSON: {json.dumps(data, indent=2)}")
            
            if data.get('status') == 'success':
                print(f"[OK] Keepalive inviato con successo! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"[WARN] Risposta server non attesa: {data}")
        except json.JSONDecodeError:
            print(f"[WARN] Risposta non JSON: {resp.text[:100]}")
    except requests.RequestException as e:
        print(f"[ERR] Keepalive fallito: {e}")
        print(f"[DEBUG] Dettagli errore: {str(e)}")


def main_loop():
    print(f"\n{'='*60}")
    print(f"AVVIO CALLHOME v2.0 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    try:
        conn = crea_connessione_db()
        if not conn:
            print("[ERR] Impossibile continuare senza connessione al database")
            return
            
        cursor = conn.cursor()
        
        print("[INFO] Inizializzazione sessione HTTP...")
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'OriBruniClient/2.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Connection': 'keep-alive',
            'Accept-Encoding': 'gzip'
        })
        print(f"[INFO] Headers HTTP: {json.dumps(dict(session.headers), indent=2)}")

        count = 0
        print(f"\n[INFO] Avvio ciclo principale con intervallo di {POLL_INTERVAL} secondi")
        print(f"{'='*60}")
        
        while True:
            count += 1
            print(f"\n[INFO] Ciclo #{count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            nome, pkey = leggi_credentials(cursor)
            if nome and pkey:
                invia_keepalive(session, nome, pkey)
            else:
                print("[ERR] Credenziali non disponibili, skip keepalive")
                
            print(f"[INFO] In attesa {POLL_INTERVAL} secondi...")
            print(f"{'- '*30}")
            time.sleep(POLL_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n[INFO] Programma interrotto manualmente")
    except mysql.connector.Error as err:
        print(f"\n[ERR] Errore database: {err}")
    except Exception as e:
        print(f"\n[ERR] Errore imprevisto: {e}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        print("[INFO] Riavvio tra 60 secondi...")
        time.sleep(60)  # Attendi prima di riavviare in caso di errore
        main_loop()  # Riavvia il loop principale


if __name__ == '__main__':
    main_loop()
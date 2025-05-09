#!/usr/bin/env python3
"""
callhome.py v3.1 - completo
Invia periodicamente un POST JSON compresso a callhome.php con keepalive e metriche di sistema.
Include gestione errori avanzata, configurazione esterna con versioning, rotating logs, dry-run, backoff, asyncio/AIOHTTP.
"""
import asyncio
import time
import os
import json
import gzip
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
import configparser
import random
import psutil
import aiomysql
import aiohttp

# Configurazione logging con rotazione
logger = logging.getLogger("callhome")
logger.setLevel(logging.INFO)
fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# Rotating file handler
fh = RotatingFileHandler('callhome.log', maxBytes=10_000_000, backupCount=5)
fh.setFormatter(fmt)
# Stream handler
sh = logging.StreamHandler()
sh.setFormatter(fmt)
logger.addHandler(fh)
logger.addHandler(sh)

# Percorso configurazione\CONFIG_FILE = Path(os.path.expanduser('~/.config/callhome/config.ini'))
CONFIG_VERSION = '1.1'
CONFIG_FILE = Path(__file__).parent / 'config.ini'

# Valori di default
DEFAULT_CONFIG = {
    'META': {'config_version': CONFIG_VERSION},
    'DATABASE': {
        'host': 'localhost',
        'port': '3306',
        'user': 'root',
        'password': 'PuhA7gWCrW',
        'database': 'OriBruniRadioControls',
        'autocommit': 'True'
    },
    'CALLHOME': {
        'url': 'https://orienteering.services/radiocontrol/callhome.php',
        'poll_interval': '20',
        'cred_check_interval': '3600',
        'max_retries': '5',
        'dry_run': 'False'
    }
}


def load_config():
    """Carica o crea config con versioning"""
    cfg = configparser.ConfigParser()
    if not CONFIG_FILE.exists():
        cfg.read_dict(DEFAULT_CONFIG)
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            cfg.write(f)
        logger.info(f"Creato file di configurazione: {CONFIG_FILE}")
    else:
        cfg.read(CONFIG_FILE)
        if not cfg.has_section('meta') or cfg.get('meta','config_version', fallback='') != CONFIG_VERSION:
            # migra aggiungendo nuove sezioni/chiavi senza sovrascrivere
            for sec, opts in DEFAULT_CONFIG.items():
                if not cfg.has_section(sec):
                    cfg[sec] = opts
                else:
                    for k, v in opts.items():
                        if not cfg.has_option(sec, k):
                            cfg.set(sec, k, v)
            cfg['meta'] = {'config_version': CONFIG_VERSION}
            with open(CONFIG_FILE, 'w') as f:
                cfg.write(f)
            logger.info("File di configurazione aggiornato alla versione %s", CONFIG_VERSION)
    return cfg


def collect_system_metrics():
    """Raccoglie metriche di sistema"""
    metrics = {}
    try:
        metrics['cpu_percent'] = psutil.cpu_percent(interval=0.5)
        vm = psutil.virtual_memory()
        metrics['memory_percent'] = vm.percent
        metrics['memory_available_mb'] = round(vm.available / (1024*1024),2)
        du = psutil.disk_usage('/')
        metrics['disk_percent'] = du.percent
        metrics['disk_free_gb'] = round(du.free/(1024*1024*1024),2)
        # uptime
        uptime_s = time.time() - psutil.boot_time()
        metrics['uptime_hours'] = round(uptime_s/3600,2)
        # load avg su Linux
        if hasattr(psutil, 'getloadavg'):
            la1, la5, la15 = psutil.getloadavg()
            metrics['load_avg_1m'] = round(la1,2)
        metrics['process_count'] = len(psutil.pids())
        # temperatura
        temps = psutil.sensors_temperatures() if hasattr(psutil, 'sensors_temperatures') else {}
        for entries in temps.values():
            if entries:
                metrics['temperature'] = round(entries[0].current,1)
                break
    except Exception as e:
        logger.warning("Errore metriche sistema: %s", e)
    return metrics


async def create_db_pool(cfg):
    db = cfg['DATABASE']
    pool = await aiomysql.create_pool(
        host=db.get('host'), port=int(db.get('port')),
        user=db.get('user'), password=db.get('password'),
        db=db.get('database'), autocommit=db.getboolean('autocommit')
    )
    return pool


async def get_credentials(pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT nome, valore FROM costanti
                WHERE nome IN ('nome','pkey')
            """)
            rows = await cur.fetchall()
    creds = {r[0]:r[1] for r in rows}
    return creds.get('nome'), creds.get('pkey')


async def send_keepalive(session, url, name, pkey, dry_run=False):
     metrics = collect_system_metrics()
     payload = {
         'name': name, 'pkey': pkey, 'action': 'keepalive',
         'timestamp': datetime.utcnow().isoformat()+'Z',
         'system_status': metrics, 'client_version': '3.1'
     }
     raw = json.dumps(payload, separators=(',',':')).encode('utf-8')
     gz = gzip.compress(raw)
     headers = {'Content-Encoding':'gzip','Content-Type':'application/json'}
     if dry_run:
         logger.info("DRY RUN - payload: %s", payload)
         return True
     try:
        # Log payload raw in caso di debug
        logger.debug("Invio payload: %s", payload)
        async with session.post(url, data=gz, headers=headers, timeout=15) as resp:
            text = await resp.text()
            if resp.status == 200:
                data = json.loads(text)
                if data.get('status')=='success':
                   logger.info("Keepalive OK: %s", data.get('message',''))
                   return True
                logger.warning("Server risponde OK ma status!='success': %s – payload era %s", data, payload)
                return False
             # qui c’è stato un errore HTTP
            logger.error("HTTP %d: %s – payload inviato: %s", resp.status, text, payload)
     except Exception as e:
        logger.error("Errore richiesta HTTP: %s – payload inviato: %s", e, payload)
     return False


async def main():
    cfg = load_config()
    ch = cfg['CALLHOME']
    url = ch.get('url')
    poll = ch.getint('poll_interval')
    cred_interval = ch.getint('cred_check_interval')
    dry_run = ch.getboolean('dry_run')
    failure_count = 0

    pool = await create_db_pool(cfg)
    async with aiohttp.ClientSession() as session:
        name = None; pkey = None; last_cred = 0
        while True:
            now = time.time()
            # aggiorna credenziali
            if not name or (now-last_cred)>=cred_interval:
                name, pkey = await get_credentials(pool)
                last_cred = now
                if not name or not pkey:
                    logger.warning("Credenziali mancanti, aspetto %ds", poll)
                    await asyncio.sleep(poll)
                    continue
            success = await send_keepalive(session, url, name, pkey, dry_run)
            # backoff su errori
            if success:
                failure_count=0; interval=poll
            else:
                failure_count+=1
                interval = min(poll*(2**failure_count), poll*10)
                logger.info("Prossimo tentativo in %ds (failure_count=%d)", interval, failure_count)
            await asyncio.sleep(interval)

if __name__=='__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Terminato dall'utente")
    except Exception as e:
        logger.critical("Errore critico: %s", e, exc_info=True)

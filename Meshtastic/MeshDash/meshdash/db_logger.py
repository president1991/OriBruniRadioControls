import sqlite3
import threading
from datetime import datetime

# Path to the SQLite database file
DB_FILE = 'messages.db'

# Lock to serialize database access across threads
_lock = threading.Lock()

def init_db():
    """
    Initialize the SQLite database and create the messages table if it doesn't exist.
    """
    with _lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Tabella esistente per messaggi
        c.execute('''
             CREATE TABLE IF NOT EXISTS messages (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 timestamp TEXT NOT NULL,
                 direction TEXT NOT NULL,
                 peer TEXT,
                 payload TEXT
             )
         ''')
        # NUOVA tabella per la telemetria strutturata
        c.execute('''
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                peer TEXT,
                uptime_seconds INTEGER,
                channel_utilization REAL,
                air_util_tx REAL,
                num_packets_tx INTEGER,
                num_packets_rx INTEGER,
                num_online_nodes INTEGER,
                num_total_nodes INTEGER,
                num_rx_dupe INTEGER,
                num_tx_relay INTEGER
            )
        ''')
        conn.commit()
        conn.close()


def log_message(direction: str, peer: str, payload: str):
    """
    Log a message to the SQLite database.

    :param direction: 'sent' or 'received'
    :param peer: identifier of the peer (e.g., node address or channel)
    :param payload: the message content
    """
    timestamp = datetime.utcnow().isoformat()
    with _lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO messages (timestamp, direction, peer, payload)
            VALUES (?, ?, ?, ?)
        ''', (timestamp, direction, peer, payload))
        conn.commit()
        conn.close()

# Nuova funzione per loggare la telemetria
def log_telemetry(peer: str, metrics: dict):
    """
    Log structured telemetry metrics for a given peer.
    metrics è il dict deviceMetrics estratto dal packet.
    """
    timestamp = datetime.utcnow().isoformat()
    with _lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO telemetry (
                timestamp, peer,
                uptime_seconds, channel_utilization, air_util_tx,
                num_packets_tx, num_packets_rx,
                num_online_nodes, num_total_nodes,
                num_rx_dupe, num_tx_relay
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, peer,
            metrics.get('uptimeSeconds'),
            metrics.get('channelUtilization'),
            metrics.get('airUtilTx'),
            metrics.get('numPacketsTx'),
            metrics.get('numPacketsRx'),
            metrics.get('numOnlineNodes'),
            metrics.get('numTotalNodes'),
            metrics.get('numRxDupe'),
            metrics.get('numTxRelay'),
        ))
        conn.commit()
        conn.close()

# Initialize the database when this module is imported
init_db()

import logging
import json
from flask import Flask, render_template, request, Response
from flask_socketio import SocketIO
import configparser
from datetime import datetime
import mysql.connector
from mysql.connector import pooling

# Configurazione logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(levelname)s: %(message)s')

# Carico la configurazione
config = configparser.ConfigParser()
config.read('config.ini')

# Prelevo i valori per il database, con valori predefiniti se non trovati
mysql_cfg = {
    'host':     'localhost',
    'port':     3306,
    'user':     'meshdash',
    'password': 'PuhA7gWCrW',  # Sostituisci con la password corretta se necessario
    'database': 'OriBruniRadioControls',
}
if 'mysql' in config:
    mysql_cfg.update({
        'host':     config['mysql'].get('host', mysql_cfg['host']),
        'port':     config['mysql'].getint('port', mysql_cfg['port']),
        'user':     config['mysql'].get('user', mysql_cfg['user']),
        'password': config['mysql'].get('password', mysql_cfg['password']),
        'database': config['mysql'].get('database', mysql_cfg['database']),
    })
else:
    logging.warning("Sezione 'mysql' non trovata in config.ini. Utilizzo valori predefiniti.")

app = Flask(__name__, static_folder='static', template_folder='templates')
socketio = SocketIO(app, cors_allowed_origins="*")

# Configurazione del pool di connessioni MySQL
def setup_db_pool():
    """Configura il pool di connessioni MySQL"""
    try:
        pool = pooling.MySQLConnectionPool(
            pool_name="meshtastic_pool",
            pool_size=5,
            host=mysql_cfg['host'],
            port=mysql_cfg['port'],
            user=mysql_cfg['user'],
            password=mysql_cfg['password'],
            database=mysql_cfg['database'],
            charset='utf8mb4'
        )
        return pool
    except Exception as e:
        logging.error(f"Errore durante la configurazione del pool MySQL: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def get_data():
    try:
        db_pool = setup_db_pool()
        if db_pool is None:
            return {'error': 'Errore di connessione al database'}, 500
        
        local_cnx = db_pool.get_connection()
        cursor = local_cnx.cursor(dictionary=True)
        
        # Fetch recent messages
        cursor.execute("SELECT * FROM messaggi ORDER BY data_ora DESC LIMIT 20")
        messaggi = cursor.fetchall()
        
        # Fetch recent punches
        cursor.execute("SELECT * FROM punches ORDER BY timestamp DESC LIMIT 20")
        punches = cursor.fetchall()
        
        # Fetch all nodes
        cursor.execute("SELECT * FROM nodes ORDER BY last_signal DESC")
        nodes = cursor.fetchall()
        
        cursor.close()
        local_cnx.close()
        
        return {'messaggi': messaggi, 'punches': punches, 'nodes': nodes}
    except Exception as e:
        app.logger.error(f"Errore durante il recupero dei dati: {e}")
        return {'error': 'Errore durante il recupero dei dati'}, 500

@app.route('/getpunches')
def get_punches():
    try:
        db_pool = setup_db_pool()
        if db_pool is None:
            app.logger.error("Errore di connessione al database: pool di connessioni non disponibile")
            return Response("Errore di connessione al database", status=500, mimetype='text/plain')
        
        local_cnx = db_pool.get_connection()
        cursor = local_cnx.cursor(dictionary=True)
        
        # Fetch all punches with specific fields
        cursor.execute("SELECT id, control, card_number, punch_time FROM punches ORDER BY id ASC")
        punches = cursor.fetchall()
        
        # Prepare CSV-like output with newline at the end of each line
        body = ""
        for punch in punches:
            body += f"{punch['id']};{punch['control']};{punch['card_number']};{punch['punch_time'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(punch['punch_time'], datetime) else punch['punch_time']}\n"
        
        cursor.close()
        local_cnx.close()
        
        return Response(body, mimetype='text/plain; charset=utf-8')
    except Exception as e:
        app.logger.error(f"Errore durante il recupero delle punzonature: {str(e)}")
        return Response(f"Errore durante il recupero delle punzonature: {str(e)}", status=500, mimetype='text/plain')

# Rinominato endpoint per compatibilità e logica aggiornata
@app.route('/getpunches.php') 
def get_punches_php():
    # Parametri da querystring
    unit_id  = request.args.get('unitId', type=int, default=None) # Ora unitId è per source_event_id
    last_id  = request.args.get('lastId', type=int, default=0)
    date_str = request.args.get('date',   default=None)
    time_str = request.args.get('time',   default=None)

    # Costruisci filtro su punch_time se passato
    use_filter_time = date_str is not None and time_str is not None
    punch_dt_filter = f"{date_str} {time_str}" if use_filter_time else None

    # Monta SQL
    # Se unitId è fornito, filtra per source_event_id. Altrimenti, prende da tutti gli eventi.
    # 'id' nella query si riferisce a punches.id (l'ID locale auto-incrementante)
    # 'record_id' nella tabella punches ora contiene l'ID originale dalla sorgente (Meshtastic o DB esterno)
    # Per coerenza con il vecchio comportamento, se vogliamo che lastId si riferisca all'ID originale,
    # dovremmo filtrare su punches.record_id > %s. Ma l'output richiede l'ID locale.
    # L'output richiesto è "id_locale;controllo;numero_carta;tempo_punzonatura"
    # Quindi, il lastId dovrebbe riferirsi a punches.id locale.

    sql_base = "SELECT id, control, card_number, punch_time FROM punches WHERE id > %s"
    params = [last_id]

    if unit_id is not None:
        sql_base += " AND source_event_id = %s"
        params.append(unit_id)
    
    if use_filter_time:
        sql_base += " AND punch_time >= %s"
        params.append(punch_dt_filter)
    
    sql_final = sql_base + " ORDER BY id ASC"

    # Esegui la query con gestione errori
    db_pool = setup_db_pool()
    if db_pool is None:
        return Response(json.dumps({"error": "Database connection error"}),
                        status=500,
                        mimetype='application/json')

    local_cnx_for_export = None
    try:
        local_cnx_for_export = db_pool.get_connection()
        cur = local_cnx_for_export.cursor()
        cur.execute(sql_final, params)
        rows = cur.fetchall()
    except mysql.connector.Error as e:
        app.logger.error(f"Errore DB /getpunches.php: {e}")
        return Response(json.dumps({"error": "Database error"}),
                        status=500,
                        mimetype='application/json')
    finally:
        if 'cur' in locals() and cur:
            cur.close()
        if local_cnx_for_export and local_cnx_for_export.is_connected():
            local_cnx_for_export.close()

    # Prepara output plain-text come l'originale
    # Formato: ID_locale;controllo;numero_scheda;tempo_punzonatura
    lines = [f"{rid};{control};{card_number};{punch_time.strftime('%Y-%m-%d %H:%M:%S') if isinstance(punch_time, datetime) else punch_time}" 
             for (rid, control, card_number, punch_time) in rows]
    body = "\n".join(lines)
    if body: # Aggiungi newline solo se c'è contenuto
        body += "\n"
        
    return Response(body, mimetype='text/plain; charset=utf-8')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)

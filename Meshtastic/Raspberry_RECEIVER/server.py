import threading
import time
import logging
import json
from flask import Flask, render_template, request, Response
from flask_socketio import SocketIO
import configparser
import mysql.connector

# Configurazione logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(levelname)s: %(message)s')

# Carico la configurazione
config = configparser.ConfigParser()
config.read('config.ini')

# Prelevo i valori
serial_port = config['serial'].get('port') or None  # se vuoto usa default del MeshtasticInterface
mysql_cfg = {
    'host':     config['mysql']['host'],
    'port':     config['mysql'].getint('port'),
    'user':     config['mysql']['user'],
    'password': config['mysql']['password'],
    'database': config['mysql']['database'],
}

from meshtastic_interface import MeshtasticInterface

app = Flask(__name__, static_folder='static', template_folder='templates')
socketio = SocketIO(app, cors_allowed_origins="*")

# Istanzio l'interfaccia Meshtastic
iface = MeshtasticInterface(port=serial_port, config={'mysql': mysql_cfg})

def background_state_updater():
    while True:
        # Accedi ai nodi tramite l'istanza interna della libreria Meshtastic (iface.iface)
        # e usa _asdict() se disponibile, o gestisci l'oggetto nodo direttamente
        nodes_data = []
        if hasattr(iface, 'iface') and iface.iface and hasattr(iface.iface, 'nodes'):
            for node_id, node_obj in iface.iface.nodes.items():
                if hasattr(node_obj, '_asdict'):
                    nodes_data.append(node_obj._asdict())
                elif isinstance(node_obj, dict):
                    nodes_data.append(node_obj)
                else:
                    # Fallback o log se il formato del nodo non è previsto
                    logging.warning(f"Formato nodo non gestito per node_id: {node_id}")
        
        # links = iface.get_links() # Assumendo che iface (MeshtasticInterface) abbia un metodo get_links()
                                  # o iface.iface.links se è un attributo diretto
        links_data = [] # Placeholder, da implementare se get_links() non esiste o va cambiato
        if hasattr(iface, 'iface') and iface.iface and hasattr(iface.iface, 'links'):
             links_data = list(iface.iface.links.values())


        socketio.emit('state_update', {'nodes': nodes_data, 'links': links_data})
        time.sleep(2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/export_punches')
def export_punches():
    # Parametri da querystring
    unit_id  = request.args.get('unitId', type=int, default=0)
    last_id  = request.args.get('lastId', type=int, default=0)
    date_str = request.args.get('date',   default=None)
    time_str = request.args.get('time',   default=None)

    # Costruisci filtro su punch_time se passato
    use_filter = date_str is not None and time_str is not None
    punch_dt   = f"{date_str} {time_str}" if use_filter else None

    # Monta SQL
    sql = (
        "SELECT id, control, card_number, punch_time"
        " FROM punches"
        " WHERE id > %s"
        "   AND record_id = %s"
    )
    params = [last_id, unit_id]
    if use_filter:
        sql += " AND punch_time >= %s"
        params.append(punch_dt)
    sql += " ORDER BY id ASC"

    # Esegui la query con gestione errori
    try:
        cnx = mysql.connector.connect(**mysql_cfg)
        cur = cnx.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
    except mysql.connector.Error as e:
        app.logger.error(f"Errore DB export_punches: {e}")
        return Response(json.dumps({"error": "Database error"}),
                        status=500,
                        mimetype='application/json')
    finally:
        if 'cur' in locals():
            cur.close()
        if 'cnx' in locals():
            cnx.close()

    # Prepara output plain-text
    lines = [f"{rid};{control};{card_number};{punch_time}" for (rid, control, card_number, punch_time) in rows]
    body = "\n".join(lines) + "\n"
    return Response(body, mimetype='text/plain; charset=utf-8')

if __name__ == '__main__':
    # Avvia thread per aggiornamenti state
    t = threading.Thread(target=background_state_updater, daemon=True)
    t.start()
    socketio.run(app, host='0.0.0.0', port=5000)

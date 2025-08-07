import glob
import logging
import sys
from datetime import datetime

# Configura logging di base per la console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.info("Avvio dello script di ascolto semplice per Meshtastic")

try:
    from meshtastic import serial_interface
    from pubsub import pub
    logging.info("Librerie Meshtastic e pubsub importate con successo")
except ImportError as e:
    logging.error("Errore durante l'importazione delle librerie: %s", str(e))
    logging.error("Installa le librerie necessarie con: sudo pip3 install meshtastic pubsub --break-system-packages")
    sys.exit(1)

try:
    import mysql.connector
    from mysql.connector import pooling
    logging.info("Librerie MySQL importate con successo")
except ImportError as e:
    logging.error("Errore durante l'importazione delle librerie MySQL: %s", str(e))
    logging.error("Installa la libreria necessaria con: sudo pip3 install mysql-connector-python --break-system-packages")
    sys.exit(1)

# Configurazione del database (da adattare in base al tuo setup)
DB_CONFIG = {
    'host': 'localhost',
    'port': '3306',
    'user': 'meshdash',
    'password': 'PuhA7gWCrW',  # Sostituisci con la password corretta
    'database': 'OriBruniRadioControls',
    'charset': 'utf8mb4'
}

def setup_db_pool():
    """Configura il pool di connessioni MySQL"""
    try:
        logging.info("Configurazione del pool di connessioni MySQL...")
        pool = pooling.MySQLConnectionPool(
            pool_name="meshtastic_pool",
            pool_size=5,
            host=DB_CONFIG['host'],
            port=int(DB_CONFIG['port']),
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG['charset']
        )
        logging.info("Pool di connessioni MySQL configurato con successo.")
        return pool
    except Exception as e:
        logging.error(f"Errore durante la configurazione del pool MySQL: {str(e)}")
        sys.exit(1)

def save_to_db(message_data, punch_data=None, hops=None, rssi=None, snr=None):
    """Salva il messaggio nel database, e se è una punzonatura anche nella tabella punches, aggiorna anche la tabella nodes"""
    try:
        db_pool = setup_db_pool() if 'db_pool' not in globals() else globals()['db_pool']
        cnx = db_pool.get_connection()
        cursor = cnx.cursor()
        
        # Salva nella tabella messaggi con i campi aggiuntivi per hops, rssi e snr
        insert_query_messaggi = (
            "INSERT INTO messaggi (data_ora, id_nodo, tipo_messaggio, timestamp_messaggio, nome_radio_control, pkey, messaggio_completo, Hops, RSSI, SNR) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        extended_message_data = message_data + (
            hops if hops != 'Non disponibile' else None,
            rssi if rssi != 'Non disponibile' else None,
            snr if snr != 'Non disponibile' else None
        )
        cursor.execute(insert_query_messaggi, extended_message_data)
        logging.info(f"Messaggio salvato nel DB (messaggi): {extended_message_data}")
        
        # Aggiorna la tabella nodes con l'ultimo segnale ricevuto dal nodo
        node_id = message_data[1]  # id_nodo
        node_name = message_data[4]  # nome_radio_control
        node_pkey = message_data[5]  # pkey
        last_signal_date = message_data[0]  # data_ora come timestamp completo
        
        # Controlla se il nodo esiste già nella tabella nodes
        check_node_query = "SELECT COUNT(*) FROM nodes WHERE id = %s"
        cursor.execute(check_node_query, (node_id,))
        node_exists = cursor.fetchone()[0] > 0
        
        if node_exists:
            # Aggiorna il record esistente
            update_node_query = (
                "UPDATE nodes SET name = %s, pkey = %s, last_signal = %s WHERE id = %s"
            )
            cursor.execute(update_node_query, (node_name, node_pkey, last_signal_date, node_id))
            logging.info(f"Nodo aggiornato nel DB (nodes): id={node_id}, name={node_name}, last_signal={last_signal_date}")
        else:
            # Inserisci un nuovo record
            insert_node_query = (
                "INSERT INTO nodes (id, name, pkey, last_signal) VALUES (%s, %s, %s, %s)"
            )
            cursor.execute(insert_node_query, (node_id, node_name, node_pkey, last_signal_date))
            logging.info(f"Nodo inserito nel DB (nodes): id={node_id}, name={node_name}, last_signal={last_signal_date}")
        
        # Se è una punzonatura (tipo_messaggio = '1'), salva anche nella tabella punches solo se non esiste già
        if punch_data:
            # Estrai i valori per il controllo di duplicati (control, card_number, punch_time)
            control = punch_data[4]  # control
            card_number = punch_data[5]  # card_number
            punch_time = punch_data[6]  # punch_time
            
            # Controlla se esiste già un record con gli stessi valori
            check_query = (
                "SELECT COUNT(*) FROM punches WHERE control = %s AND card_number = %s AND punch_time = %s"
            )
            cursor.execute(check_query, (control, card_number, punch_time))
            result = cursor.fetchone()
            
            if result[0] > 0:
                logging.info(f"Punzonatura già esistente nel DB (punches), non salvata: control={control}, card_number={card_number}, punch_time={punch_time}")
            else:
                insert_query_punches = (
                    "INSERT INTO punches (timestamp, name, pkey, record_id, control, card_number, punch_time, raw) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                )
                cursor.execute(insert_query_punches, punch_data)
                logging.info(f"Punzonatura salvata nel DB (punches): {punch_data}")
        
        cnx.commit()
        cursor.close()
        cnx.close()
    except Exception as e:
        logging.error(f"Errore durante il salvataggio nel DB: {str(e)}")

def on_receive(packet, interface):
    """Gestore per i pacchetti ricevuti, mostra tutti i messaggi inclusi JSON e salva solo quelli con tipo_messaggio nel DB"""
    try:
        # Formatta il timestamp in italiano (dd/mm/yyyy hh:mm:ss)
        timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        from_id = packet.get('fromId', 'Unknown')
        raw_message = ""
        tipo_messaggio = ""
        timestamp_messaggio = ""
        nome_radio_control = ""
        pkey = ""
        hop_limit = packet.get('hopLimit', 'Non disponibile')
        hop_start = packet.get('hopStart', 'Non disponibile')
        rssi = packet.get('rxRssi', 'Non disponibile')
        snr = packet.get('rxSnr', 'Non disponibile')
        hops = 'Non disponibile'
        if hop_limit != 'Non disponibile' and hop_start != 'Non disponibile':
            hops = hop_start - hop_limit if hop_start >= hop_limit else 0
        signal_info = f"RSSI: {rssi}, SNR: {snr}"
        
        if 'decoded' in packet:
            if 'text' in packet['decoded']:
                text_message = packet['decoded']['text']
                logging.info(f"[{timestamp}] Messaggio testuale da {from_id} (Hops: {hops}, {signal_info}): {text_message}")
                raw_message = text_message
                parts = text_message.split(';')
                if len(parts) > 0:
                    tipo_messaggio = parts[0]
                    timestamp_messaggio = parts[1] if len(parts) > 1 else ""
                    nome_radio_control = parts[2] if len(parts) > 2 else ""
                    pkey = parts[3] if len(parts) > 3 else ""
            elif 'payload' in packet['decoded']:
                try:
                    # Prova a decodificare il payload come stringa
                    payload = packet['decoded']['payload']
                    if isinstance(payload, bytes):
                        payload_str = payload.decode('utf-8', errors='ignore')
                    else:
                        payload_str = str(payload)
                    
                    # Prova a parsare come JSON se possibile
                    import json
                    try:
                        json_data = json.loads(payload_str)
                        logging.info(f"[{timestamp}] Messaggio JSON da {from_id} (Hops: {hops}, {signal_info}): {json.dumps(json_data, indent=2)}")
                        raw_message = payload_str
                    except json.JSONDecodeError:
                        logging.info(f"[{timestamp}] Messaggio non-JSON da {from_id} (Hops: {hops}, {signal_info}): {payload_str}")
                        raw_message = payload_str
                except Exception as e:
                    logging.error(f"[{timestamp}] Errore decodifica payload da {from_id}: {str(e)}")
                    raw_message = str(packet['decoded']['payload'])
            else:
                logging.info(f"[{timestamp}] Messaggio decodificato da {from_id} (Hops: {hops}, {signal_info}): {packet['decoded']}")
                raw_message = str(packet['decoded'])
        else:
            logging.info(f"[{timestamp}] Messaggio non decodificato da {from_id} (Hops: {hops}, {signal_info}): {packet}")
            raw_message = str(packet)
        
        # Salva il messaggio nel database solo se ha un tipo_messaggio
        if tipo_messaggio:
            message_data = (
                datetime.now(),
                from_id,
                tipo_messaggio,
                timestamp_messaggio,
                nome_radio_control,
                pkey,
                raw_message
            )
            punch_data = None
            # Se il tipo_messaggio è '1', salva anche nella tabella punches come punzonatura
            if tipo_messaggio == '1' and len(parts) >= 8:
                punch_data = (
                    datetime.now(),
                    nome_radio_control,  # name
                    pkey,  # pkey
                    parts[4] if len(parts) > 4 else "",  # record_id
                    parts[5] if len(parts) > 5 else "",  # control
                    parts[6] if len(parts) > 6 else "",  # card_number
                    parts[7] if len(parts) > 7 else "",  # punch_time
                    raw_message  # raw
                )
            save_to_db(message_data, punch_data, hops, rssi, snr)
        else:
            logging.info(f"[{timestamp}] Messaggio non salvato nel DB, manca tipo_messaggio: {raw_message}")
    except Exception as e:
        logging.error(f"Errore durante l'elaborazione del pacchetto: {str(e)}")

def main():
    try:
        # Controlla se una porta è stata specificata come argomento della riga di comando
        import sys
        port = None
        if len(sys.argv) > 1:
            port = sys.argv[1]
            logging.info(f"Porta specificata manualmente: {port}")
        else:
            # Cerca la porta seriale del dispositivo Meshtastic
            for path in glob.glob('/dev/serial/by-id/*'):
                if 'CP2102' in path or 'Meshtastic' in path:
                    port = path
                    break
            
            if not port:
                logging.critical("Nessuna porta Meshtastic trovata su /dev/serial/by-id. Assicurati che il dispositivo sia collegato.")
                logging.info("Puoi specificare manualmente una porta con: python3 simple_meshtastic_listener.py <porta>")
                logging.info("Per elencare le porte disponibili, usa: ls /dev/tty*")
                sys.exit(1)
            
            logging.info(f"Porta Meshtastic rilevata: {port}")
        
        # Connetti al dispositivo
        logging.info(f"Connessione alla porta: {port}")
        iface = serial_interface.SerialInterface(devPath=port)
        logging.info("Connessione riuscita")
        
        # Sottoscrivi al canale di ricezione dei messaggi
        logging.info("Registrazione del callback per i messaggi ricevuti")
        pub.subscribe(on_receive, "meshtastic.receive")
        logging.info("Sottoscrizione completata. In attesa di messaggi...")
        
        # Mantieni lo script in esecuzione
        import time
        while True:
            time.sleep(1)
    except Exception as e:
        logging.error(f"Errore durante l'esecuzione dello script: {str(e)}")
        logging.info("Se la porta è occupata, prova a liberarla con: sudo fuser -k <porta>")
        logging.info("Puoi specificare manualmente una porta con: python3 simple_meshtastic_listener.py <porta>")
        logging.info("Per elencare le porte disponibili, usa: ls /dev/tty*")
        sys.exit(1)

if __name__ == "__main__":
    main()

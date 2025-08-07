import glob
import logging
import os
import sys
import traceback
from datetime import datetime
try:
    import mysql.connector
    from mysql.connector import pooling
    from meshtastic import serial_interface
    from pubsub import pub # AGGIUNTO import per pubsub
    logging.info("Importazioni di librerie completate con successo")
except Exception as e:
    logging.error("Errore durante l'importazione delle librerie: %s", str(e))
    logging.error("Traceback completo: %s", traceback.format_exc())
    sys.exit(1)

# Configura il logging su file per catturare tutti i messaggi, anche in caso di crash immediato
log_file_path = "/tmp/meshtastic_interface_detailed.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)
logging.info("Logging configurato su file: %s", log_file_path)

# Costante per il tipo "punches"
PUNCHES_TYPE = '1'
TELEMETRY_MESSAGE_TYPE = '0' # Definiamo il tipo per i messaggi di telemetria

def main():
    try:
        # Qui andrebbe il codice per leggere la configurazione e inizializzare la classe
        logging.info("Inizio del blocco main")
        # Simuliamo un'istanza della classe per il test, in realtà dovresti leggere 'port' e 'config'
        interface = MeshtasticInterface(port=None, config={'mysql': {'host': 'localhost', 'port': '3306', 'user': 'user', 'password': 'pass', 'database': 'db'}})
        logging.info("Istanza di MeshtasticInterface creata con successo")
        # Mantieni il processo in esecuzione per ricevere messaggi
        import time
        while True:
            time.sleep(1)
    except Exception as e:
        logging.error("Errore nel blocco main: %s", str(e))
        logging.error("Traceback completo: %s", traceback.format_exc())
        sys.exit(1)

class MeshtasticInterface:
    def __init__(self, port, config):
        self.telemetry_nodes = {} # Dizionario per memorizzare i dati dei nodi dalla telemetria
        logging.info("Inizializzazione di MeshtasticInterface")
        # Se non è specificata una porta, tenta di rilevarla via /dev/serial/by-id
        if not port:
            detected = None
            logging.info("Ricerca porta Meshtastic su /dev/serial/by-id")
            for path in glob.glob('/dev/serial/by-id/*'):
                if 'CP2102' in path or 'Meshtastic' in path:
                    detected = path
                    break
            if not detected:
                logging.critical("Nessuna porta Meshtastic trovata su /dev/serial/by-id")
                raise RuntimeError("Nessuna porta Meshtastic trovata. Assicurati di collegare il dispositivo Meshtastic.")
            logging.info(f"[mesh] Porta Meshtastic rilevata: {detected}")
            port = detected
        else:
            logging.info(f"Porta specificata manualmente: {port}")

        # Istanzia l'interfaccia serale con la porta (determinata o passata)
        logging.info(f"Tentativo di connessione alla porta: {port}")
        try:
            self.iface = serial_interface.SerialInterface(devPath=port) # Argomento corretto è devPath
            logging.info("Connessione alla porta riuscita")
        except Exception as e:
            logging.error(f"Errore durante la connessione alla porta {port}: {str(e)}")
            raise

        # Pool di connessioni MySQL
        logging.info("Configurazione del pool di connessioni MySQL")
        try:
            self.mysql_pool = pooling.MySQLConnectionPool(
                pool_name="meshdash_pool",
                pool_size=5,
                host=config['mysql']['host'],
                port=int(config['mysql']['port']),
                user=config['mysql']['user'],
                password="****",  # Nascondi la password nei log
                database=config['mysql']['database'],
                charset='utf8mb4'
            )
            logging.info("Pool di connessioni MySQL configurato con successo")
        except Exception as e:
            logging.error(f"Errore durante la configurazione del pool MySQL: {str(e)}")
            raise

        # Registriamo il callback per i pacchetti ricevuti usando pubsub
        # self.iface.onReceiveTxPacket(self._on_receive) # VECCHIO MODO
        logging.info("Registrazione del callback per i pacchetti ricevuti")
        try:
            pub.subscribe(self._on_receive, "meshtastic.receive") # NUOVO MODO con pubsub
            logging.info("Sottoscrizione a meshtastic.receive completata.")
        except Exception as e:
            logging.error(f"Errore durante la sottoscrizione a meshtastic.receive: {str(e)}")
            raise

    def _on_receive(self, packet, interface): # La firma dovrebbe essere compatibile
        """
        Packet handler: prende payload formattato con ';', salva sempre il messaggio
        in messages, e se è punches anche in punches.
        """
        payload = packet.get('payload', '')
        parts = payload.split(';')
        if not parts:
            return

        msg_type = parts[0]
        # Timestamp per inserimento in messages
        ts_msg = datetime.utcnow()
        # Prepara valori per messages: f1, f2, f3 dopo il tipo
        # _, f1, f2, f3 = parts[:4] # Vecchio parsing generico

        # Nuovo parsing basato su msg_type
        f1, f2, f3 = None, None, None # Default
        if len(parts) > 1: f1 = parts[1]
        if len(parts) > 2: f2 = parts[2]
        if len(parts) > 3: f3 = parts[3]

        node_id_from_packet = packet.get('from') # ID numerico del nodo mittente
        node_eui_from_packet = packet.get('source', {}).get('properties', {}).get('node_eui', 'UNKNOWN_NODE_EUI')
        logging.info(f"Payload ricevuto: {payload}")


        # Gestione specifica per messaggi di telemetria
        if msg_type == TELEMETRY_MESSAGE_TYPE and len(parts) >= 4:
            try:
                telemetry_timestamp_str = parts[1]
                telemetry_node_name = parts[2]
                telemetry_pkey = parts[3] # Questo dovrebbe essere l'ID univoco del dispositivo, es. !aabbccdd

                # Usiamo l'ID del nodo dal pacchetto Meshtastic come chiave primaria se disponibile,
                # altrimenti la pkey dal messaggio. L'ID del pacchetto è più affidabile.
                key_node_id = node_id_from_packet 
                if not key_node_id: # Fallback se 'from' non è nel pacchetto
                    try: # La pkey potrebbe essere l'ID esadecimale del nodo senza '!'
                        key_node_id = int(telemetry_pkey.replace("!", ""), 16)
                    except:
                        key_node_id = telemetry_pkey # Usa la pkey come stringa se non convertibile

                self.telemetry_nodes[key_node_id] = {
                    'longName': telemetry_node_name,
                    'id': telemetry_pkey, # Questo è l'ID stringa come !aabbccdd
                    'num': node_id_from_packet, # ID numerico Meshtastic
                    'last_seen_telemetry': datetime.fromtimestamp(float(telemetry_timestamp_str)).isoformat() if telemetry_timestamp_str else ts_msg.isoformat(),
                    'raw_telemetry_payload': payload
                }
                logging.info(f"Aggiornati dati telemetria per nodo {key_node_id}: {self.telemetry_nodes[key_node_id]}")
            except IndexError:
                logging.warning(f"Messaggio di telemetria malformato ricevuto: {payload}")
            except Exception as e:
                logging.error(f"Errore nel parsing del messaggio di telemetria {payload}: {e}")

        # Inserimento in messages per tutti i tipi
        cnx = None  # Inizializza cnx a None
        try:
            cnx = self.mysql_pool.get_connection()
            cursor = cnx.cursor()
            insert_msgs = (
                "INSERT INTO messages"
                " (timestamp, node_eui, field1, field2, field3, raw)"
                " VALUES (%s, %s, %s, %s, %s, %s)"
            )
            cursor.execute(insert_msgs, (
                ts_msg,
                node_eui_from_packet,
                f1, f2, f3, # Questi sono i campi generici dal payload
                payload
            ))
            logging.info(f"Inserito messaggio in DB: timestamp={ts_msg}, node_eui={node_eui_from_packet}, field1={f1}, field2={f2}, field3={f3}, raw={payload}")

            # Se è punches (diverso da telemetria), inserisci anche in punches
            if msg_type == PUNCHES_TYPE and msg_type != TELEMETRY_MESSAGE_TYPE: # Assicurati che non sia un messaggio di telemetria
                # Il parsing per punches rimane lo stesso, ma assicurati che parts abbia abbastanza elementi
                # Questo parsing era già presente, lo manteniamo per i messaggi di tipo PUNCHES_TYPE
                current_parts_for_punch = payload.split(';') # Riparsiamo per pulizia
                if len(current_parts_for_punch) >= 8 : # Deve avere almeno 8 campi per i punch
                    _, ts_str, name, pkey, rec_id, control, card_number, punch_time = current_parts_for_punch[:8]
                else:
                    # Logga un errore o gestisci il caso di messaggio punch malformato
                    logging.warning(f"Messaggio PUNCHES malformato o con campi insufficienti: {payload}")
                    # Potresti voler saltare l'inserimento o inserire NULL dove possibile
                    # Per ora, saltiamo se malformato per evitare errori SQL
                    # Questo return esce solo dalla parte di inserimento punch
                    # return # Commentato per permettere il commit dell'insert in messages

            # Se è punches, inserisci anche in punches (CODICE ORIGINALE, DA RIVEDERE CON IL NUOVO PARSING)
            # Questo blocco va integrato meglio con il parsing sopra
            if msg_type == PUNCHES_TYPE: # Questo if è ridondante se già gestito sopra
                # Assumiamo che parts sia già stato popolato correttamente per PUNCHES_TYPE
                # e che il controllo sulla lunghezza sia già stato fatto.
                # La logica di parsing per PUNCHES_TYPE deve essere chiara e distinta.
                # Per ora, commento il blocco originale per evitare confusione con il nuovo parsing.
                # while len(parts) < 8:
                #    parts.append(None)
                # _, ts_str, name, pkey, rec_id, control, card_number, punch_time = parts[:8]
                
                # Ricontrolliamo la lunghezza di 'parts' specificamente per PUNCHES_TYPE
                # Questo è un refactoring del blocco precedente per chiarezza
                punch_parts = payload.split(';')
                if punch_parts[0] == PUNCHES_TYPE and len(punch_parts) >= 8:
                    _, ts_str, name, pkey_punch, rec_id, control, card_number, punch_time = punch_parts[:8]
                try:
                    ts_p = datetime.fromisoformat(ts_str)
                except Exception:
                    ts_p = datetime.utcnow()

                # Non c'è bisogno di prendere una nuova connessione se usi la stessa
                insert_punch = (
                    "INSERT INTO punches"
                    " (timestamp, name, pkey, record_id, control, card_number, punch_time, raw)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                )
                cursor.execute(insert_punch, (
                    ts_p,
                    name,
                    pkey,
                    rec_id,
                    control,
                    card_number,
                    punch_time,
                    payload
                ))
            
            cnx.commit() # Commit alla fine dopo tutte le operazioni
            cursor.close()

        except mysql.connector.Error as err:
            logging.error(f"Errore MySQL in _on_receive: {err}")
        except Exception as e:
            logging.error(f"Errore generico in _on_receive: {e}")
        finally:
            if cnx and cnx.is_connected(): # Assicurati che la connessione esista e sia aperta prima di chiuderla
                cnx.close()
                logging.debug("Connessione MySQL restituita al pool.")

# Note: Assicurati di aver creato le tabelle SQL:
#
# CREATE TABLE messages (
#   id INT AUTO_INCREMENT PRIMARY KEY,
#   timestamp DATETIME NOT NULL,
#   node_eui VARCHAR(32),
#   field1 VARCHAR(255),
#   field2 VARCHAR(255),
#   field3 VARCHAR(255),
#   raw TEXT
# );
#
# CREATE TABLE punches (
#   id INT AUTO_INCREMENT PRIMARY KEY,
#   timestamp DATETIME NOT NULL,
#   name VARCHAR(255),
#   pkey VARCHAR(255),
#   record_id VARCHAR(255),
#   control VARCHAR(255),
#   card_number VARCHAR(255),
#   punch_time VARCHAR(255),
#   raw TEXT
# );

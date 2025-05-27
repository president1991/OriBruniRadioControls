import glob
import logging
import mysql.connector
from mysql.connector import pooling
from datetime import datetime
from meshtastic import serial_interface

# Costante per il tipo "punches"
PUNCHES_TYPE = '1'

class MeshtasticInterface:
    def __init__(self, port, config):
        # Se non è specificata una porta, tenta di rilevarla via /dev/serial/by-id
        if not port:
            detected = None
            for path in glob.glob('/dev/serial/by-id/*'):
                if 'CP2102' in path or 'Meshtastic' in path:
                    detected = path
                    break
            if not detected:
                logging.critical("Nessuna porta Meshtastic trovata su /dev/serial/by-id")
                raise RuntimeError("Nessuna porta Meshtastic trovata. Assicurati di collegare il dispositivo Meshtastic.")
            logging.info(f"[mesh] Porta Meshtastic rilevata: {detected}")
            port = detected

        # Istanzia l'interfaccia serale con la porta (determinata o passata)
        self.iface = serial_interface.SerialInterface(port=port)

        # Pool di connessioni MySQL
        self.mysql_pool = pooling.MySQLConnectionPool(
            pool_name="meshdash_pool",
            pool_size=5,
            host=config['mysql']['host'],
            port=int(config['mysql']['port']),
            user=config['mysql']['user'],
            password=config['mysql']['password'],
            database=config['mysql']['database'],
            charset='utf8mb4'
        )

        # Registriamo il callback per i pacchetti ricevuti
        self.iface.onReceiveTxPacket(self._on_receive)

    def _on_receive(self, packet, interface):
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
        while len(parts) < 4:
            parts.append(None)
        _, f1, f2, f3 = parts[:4]

        # Inserimento in messages per tutti i tipi
        cnx = self.mysql_pool.get_connection()
        cursor = cnx.cursor()
        insert_msgs = (
            "INSERT INTO messages"
            " (timestamp, node_eui, field1, field2, field3, raw)"
            " VALUES (%s, %s, %s, %s, %s, %s)"
        )
        cursor.execute(insert_msgs, (
            ts_msg,
            packet.get('source', {})
                  .get('properties', {})
                  .get('node_eui'),
            f1, f2, f3,
            payload
        ))
        cnx.commit()
        cursor.close()
        cnx.close()

        # Se è punches, inserisci anche in punches
        if msg_type == PUNCHES_TYPE:
            while len(parts) < 8:
                parts.append(None)
            _, ts_str, name, pkey, rec_id, control, card_number, punch_time = parts[:8]
            try:
                ts_p = datetime.fromisoformat(ts_str)
            except Exception:
                ts_p = datetime.utcnow()

            cnx = self.mysql_pool.get_connection()
            cursor = cnx.cursor()
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
            cnx.commit()
            cursor.close()
            cnx.close()

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

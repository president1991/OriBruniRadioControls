import logging
import time
import json
import os
import mysql.connector
from datetime import datetime

# Nome del file per salvare lo stato della sincronizzazione (ultimo ID processato per ogni race_group)
STATUS_FILE_DEFAULT = 'external_sync_status.json'

class ExternalDBSync:
    def __init__(self, external_db_config, local_mysql_pool, status_file_path=None):
        self.external_db_config = external_db_config
        self.local_mysql_pool = local_mysql_pool
        self.status_file = status_file_path or os.path.join(os.path.dirname(__file__), STATUS_FILE_DEFAULT)
        self.last_ids_processed = self._load_status()
        self.table_name = external_db_config.get('table_name', 'radiocontrol')
        logging.info(f"ExternalDBSync inizializzato. Tabella esterna: {self.table_name}, File di stato: {self.status_file}")

    def _load_status(self):
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r') as f:
                    status = json.load(f)
                    logging.info(f"Stato di sincronizzazione caricato: {status}")
                    return {int(k): v for k, v in status.items()} # Assicura che race_group sia int
            return {}
        except Exception as e:
            logging.error(f"Errore durante il caricamento dello stato di sincronizzazione: {e}")
            return {}

    def _save_status(self):
        try:
            with open(self.status_file, 'w') as f:
                json.dump(self.last_ids_processed, f)
            logging.info(f"Stato di sincronizzazione salvato: {self.last_ids_processed}")
        except Exception as e:
            logging.error(f"Errore durante il salvataggio dello stato di sincronizzazione: {e}")

    def _get_external_db_connection(self):
        try:
            cnx = mysql.connector.connect(
                host=self.external_db_config['host'],
                port=int(self.external_db_config.get('port', 3306)),
                user=self.external_db_config['user'],
                password=self.external_db_config['password'],
                database=self.external_db_config['database'],
                charset='utf8mb4'
            )
            logging.info(f"Connesso al DB esterno {self.external_db_config['host']}/{self.external_db_config['database']}")
            return cnx
        except mysql.connector.Error as err:
            logging.error(f"Errore di connessione al DB esterno: {err}")
            return None

    def sync_punches(self):
        logging.info("Avvio sincronizzazione punches da DB esterno...")
        ext_cnx = self._get_external_db_connection()
        if not ext_cnx:
            return

        local_cnx = None
        new_punches_count = 0

        try:
            ext_cursor = ext_cnx.cursor(dictionary=True)
            
            # Ottieni tutti i race_group unici dalla tabella esterna
            # O potremmo decidere di sincronizzare solo quelli per cui abbiamo già uno stato
            # Per ora, prendiamo tutti i race_group presenti.
            # Se la tabella è molto grande, questo potrebbe essere inefficiente.
            # Sarebbe meglio avere una lista predefinita di race_group da sincronizzare o un modo per scoprirli.
            # Per semplicità, per ora non interroghiamo i race_group distinti.
            # Assumiamo che se un race_group ha dati, lo troveremo.

            # Per ogni race_group di cui teniamo traccia (o per quelli nuovi che troviamo)
            # Questo approccio non scopre nuovi race_group automaticamente.
            # Per scoprire nuovi race_group, dovremmo fare una query tipo SELECT DISTINCT race_group FROM self.table_name
            # e poi iterare. Per ora, semplifichiamo e assumiamo che i race_group da tracciare siano quelli
            # già presenti in self.last_ids_processed o un default se è vuoto (es. event_id da config).
            
            # Se non ci sono race_group tracciati, potremmo usare un default da config.ini
            # Per ora, se last_ids_processed è vuoto, non farà nulla.
            # Modifichiamo per prendere un race_group di default se non ci sono stati.
            
            race_groups_to_sync = list(self.last_ids_processed.keys())
            if not race_groups_to_sync and 'default_race_group_to_sync' in self.external_db_config:
                 try:
                     race_groups_to_sync.append(int(self.external_db_config['default_race_group_to_sync']))
                 except ValueError:
                     logging.warning("default_race_group_to_sync non è un intero valido.")
            
            # Per sincronizzare TUTTI i race_group, dovremmo prima fare:
            # ext_cursor.execute(f"SELECT DISTINCT race_group FROM {self.table_name} WHERE race_group IS NOT NULL")
            # race_groups_to_sync = [row['race_group'] for row in ext_cursor.fetchall()]
            # Per ora, manteniamo la logica più semplice basata sugli ID già tracciati o un default.
            # Se vuoi sincronizzare tutti gli eventi, la logica qui andrebbe espansa.
            # Dato il tuo feedback "puoi anche scaricare i dati di tutti gli eventi", modifichiamo:

            ext_cursor.execute(f"SELECT DISTINCT race_group FROM {self.table_name} WHERE race_group IS NOT NULL")
            all_race_groups_in_external_db = [row['race_group'] for row in ext_cursor.fetchall()]
            logging.info(f"Trovati race_group nel DB esterno: {all_race_groups_in_external_db}")

            for race_group_id in all_race_groups_in_external_db:
                last_id = self.last_ids_processed.get(race_group_id, 0)
                logging.info(f"Sincronizzazione per race_group {race_group_id}, ultimo ID processato: {last_id}")

                query = (
                    f"SELECT id, control, card_number, punch_time, timestamp as external_timestamp "
                    f"FROM {self.table_name} "
                    f"WHERE race_group = %s AND id > %s "
                    f"ORDER BY id ASC"
                )
                ext_cursor.execute(query, (race_group_id, last_id))
                
                rows_to_insert = []
                max_id_in_batch = last_id

                for row in ext_cursor:
                    rows_to_insert.append((
                        row['external_timestamp'], # timestamp (data/ora evento nel DB esterno)
                        None, # name (da definire, forse race_group_id o un nome evento)
                        None, # pkey (da definire)
                        row['id'],       # record_id (ID originale dal DB esterno)
                        row['control'],
                        row['card_number'],
                        row['punch_time'],
                        f"EXT_DB_SYNC;RG={race_group_id};ID={row['id']}", # raw
                        race_group_id # source_event_id
                    ))
                    if row['id'] > max_id_in_batch:
                        max_id_in_batch = row['id']
                
                if rows_to_insert:
                    local_cnx = self.local_mysql_pool.get_connection()
                    local_cursor = local_cnx.cursor()
                    
                    # Assicurati che la tabella punches abbia la colonna source_event_id
                    insert_query = (
                        "INSERT INTO punches (timestamp, name, pkey, record_id, control, card_number, punch_time, raw, source_event_id) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                    )
                    local_cursor.executemany(insert_query, rows_to_insert)
                    local_cnx.commit()
                    new_punches_count += local_cursor.rowcount
                    logging.info(f"Inseriti {local_cursor.rowcount} nuovi punches per race_group {race_group_id} nel DB locale.")
                    local_cursor.close()
                    if local_cnx and local_cnx.is_connected():
                        local_cnx.close()
                    
                    self.last_ids_processed[race_group_id] = max_id_in_batch
                    self._save_status()
            
            if new_punches_count > 0:
                 logging.info(f"Sincronizzazione completata. Totale nuovi punches inseriti: {new_punches_count}")
            else:
                 logging.info("Nessun nuovo punch da sincronizzare.")

        except mysql.connector.Error as err:
            logging.error(f"Errore MySQL durante la sincronizzazione: {err}")
        except Exception as e:
            logging.error(f"Errore generico durante la sincronizzazione: {e}")
        finally:
            if ext_cnx and ext_cnx.is_connected():
                ext_cnx.close()
                logging.info("Connessione al DB esterno chiusa.")
            # local_cnx viene chiuso nel blocco try se aperto

def run_sync_periodically(external_db_config, local_mysql_pool, sync_interval_seconds, status_file_path=None):
    syncer = ExternalDBSync(external_db_config, local_mysql_pool, status_file_path)
    while True:
        try:
            syncer.sync_punches()
        except Exception as e:
            logging.error(f"Errore nel ciclo di sincronizzazione periodica: {e}")
        logging.debug(f"Attesa di {sync_interval_seconds} secondi per la prossima sincronizzazione...")
        time.sleep(sync_interval_seconds)

if __name__ == '__main__':
    # Questo blocco è solo per testare lo script standalone
    # In produzione, run_sync_periodically sarà chiamato da server.py
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s (%(module)s): %(message)s')
    
    # Configurazione di esempio per test standalone
    # Dovrai creare un config_test.ini o passare i dati direttamente
    # Per ora, usiamo valori hardcoded per il test
    mock_external_db_cfg = {
        'host': '195.231.61.119', 'port': 3306, 'user': 'oribrunipro',
        'password': 'zHA9IxV7WwKi6Ioxjh0q', 'database': 'oribruniradiocontrols',
        'table_name': 'radiocontrol'
    }
    
    # Per testare, avremmo bisogno di un mock del pool di connessioni MySQL locale
    # o di una vera istanza. Per semplicità, questo test non si connetterà al DB locale.
    class MockMySQLPool:
        def get_connection(self):
            logging.warning("Usando MockMySQLPool: nessuna operazione reale sul DB locale.")
            class MockCnx:
                def cursor(self): return MockCursor()
                def commit(self): pass
                def close(self): pass
                def is_connected(self): return False
            class MockCursor:
                rowcount = 0
                def execute(self, q, p): pass
                def executemany(self, q, p): self.rowcount = len(p) if p else 0
                def close(self): pass
            return MockCnx()

    mock_local_pool = MockMySQLPool()
    
    test_sync_interval = 10 
    logging.info(f"Avvio test di ExternalDBSync con intervallo di {test_sync_interval}s...")
    syncer_test = ExternalDBSync(mock_external_db_cfg, mock_local_pool, 'external_sync_status_test.json')
    syncer_test.sync_punches()
    logging.info("Test di sincronizzazione completato.")

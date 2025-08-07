#!/usr/bin/env python3
"""
Database Manager per OriBruniRadioControls
Gestisce connessioni database sicure con context manager e pool ottimizzato
"""

import logging
import threading
import time
from contextlib import contextmanager
from typing import Dict, Any, Optional, List, Tuple
import mysql.connector
from mysql.connector import pooling, Error as MySQLError
from mysql.connector.cursor import MySQLCursor
from config_manager import ConfigManager

class DatabaseManager:
    """Gestione sicura e ottimizzata delle connessioni database"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.pool = None
        self._lock = threading.RLock()
        self._setup_pool()
        self._setup_logging()
    
    def _setup_logging(self):
        """Configura logging specifico per database"""
        self.logger = logging.getLogger('DatabaseManager')
        self.logger.setLevel(logging.INFO)
    
    def _setup_pool(self):
        """Configura il pool di connessioni MySQL"""
        try:
            db_config = self.config_manager.get_database_config()
            pool_config = {
                'pool_name': self.config_manager.get('DATABASE', 'pool_name', 'oribruni_pool'),
                'pool_size': self.config_manager.getint('DATABASE', 'pool_size', 5),
                'pool_reset_session': True,
                'autocommit': db_config.get('autocommit', True),
                'charset': 'utf8mb4',
                'collation': 'utf8mb4_unicode_ci',
                'time_zone': '+00:00',
                'sql_mode': 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO',
                'raise_on_warnings': True
            }
            
            # Merge configurazioni
            pool_config.update(db_config)
            
            self.pool = pooling.MySQLConnectionPool(**pool_config)
            self.logger.info(f"Pool database creato: {pool_config['pool_name']} (size: {pool_config['pool_size']})")
            
            # Test connessione
            self._test_connection()
            
        except Exception as e:
            self.logger.error(f"Errore creazione pool database: {e}")
            raise
    
    def _test_connection(self):
        """Testa la connessione al database"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    if result[0] != 1:
                        raise Exception("Test connessione fallito")
            self.logger.info("Test connessione database: OK")
        except Exception as e:
            self.logger.error(f"Test connessione database fallito: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager per connessioni database sicure"""
        conn = None
        try:
            with self._lock:
                conn = self.pool.get_connection()
            
            # Verifica stato connessione
            if not conn.is_connected():
                conn.reconnect(attempts=3, delay=1)
            
            yield conn
            
        except MySQLError as e:
            self.logger.error(f"Errore MySQL: {e}")
            if conn and conn.is_connected():
                try:
                    conn.rollback()
                except:
                    pass
            raise
        except Exception as e:
            self.logger.error(f"Errore database generico: {e}")
            if conn and conn.is_connected():
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if conn and conn.is_connected():
                try:
                    conn.close()
                except Exception as e:
                    self.logger.warning(f"Errore chiusura connessione: {e}")
    
    @contextmanager
    def get_cursor(self, dictionary=False, buffered=True):
        """Context manager per cursor database sicuri"""
        with self.get_connection() as conn:
            cursor = None
            try:
                cursor = conn.cursor(dictionary=dictionary, buffered=buffered)
                yield cursor, conn
                conn.commit()
            except Exception as e:
                if conn.is_connected():
                    conn.rollback()
                raise
            finally:
                if cursor:
                    cursor.close()
    
    def execute_query(self, query: str, params: Tuple = None, fetch_one: bool = False, 
                     fetch_all: bool = False, dictionary: bool = False) -> Any:
        """Esegue una query con gestione errori robusta"""
        try:
            with self.get_cursor(dictionary=dictionary) as (cursor, conn):
                cursor.execute(query, params or ())
                
                if fetch_one:
                    return cursor.fetchone()
                elif fetch_all:
                    return cursor.fetchall()
                else:
                    return cursor.rowcount
                    
        except MySQLError as e:
            self.logger.error(f"Errore esecuzione query: {e}")
            self.logger.error(f"Query: {query}")
            self.logger.error(f"Params: {params}")
            raise
    
    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """Esegue query multiple con transazione"""
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.executemany(query, params_list)
                return cursor.rowcount
        except MySQLError as e:
            self.logger.error(f"Errore esecuzione query multiple: {e}")
            raise
    
    def insert_record(self, table: str, data: Dict[str, Any]) -> Optional[int]:
        """Inserisce un record e restituisce l'ID"""
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(query, tuple(data.values()))
                return cursor.lastrowid
        except MySQLError as e:
            self.logger.error(f"Errore inserimento in {table}: {e}")
            raise
    
    def update_record(self, table: str, data: Dict[str, Any], where_clause: str, 
                     where_params: Tuple = None) -> int:
        """Aggiorna record e restituisce il numero di righe modificate"""
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        params = tuple(data.values()) + (where_params or ())
        
        try:
            return self.execute_query(query, params)
        except MySQLError as e:
            self.logger.error(f"Errore aggiornamento {table}: {e}")
            raise
    
    def delete_record(self, table: str, where_clause: str, where_params: Tuple = None) -> int:
        """Elimina record e restituisce il numero di righe eliminate"""
        query = f"DELETE FROM {table} WHERE {where_clause}"
        
        try:
            return self.execute_query(query, where_params)
        except MySQLError as e:
            self.logger.error(f"Errore eliminazione da {table}: {e}")
            raise
    
    def get_table_info(self, table: str) -> List[Dict[str, Any]]:
        """Ottiene informazioni sulla struttura di una tabella"""
        query = f"DESCRIBE {table}"
        return self.execute_query(query, fetch_all=True, dictionary=True)
    
    def check_table_exists(self, table: str) -> bool:
        """Verifica se una tabella esiste"""
        query = """
        SELECT COUNT(*) as count 
        FROM information_schema.tables 
        WHERE table_schema = DATABASE() AND table_name = %s
        """
        result = self.execute_query(query, (table,), fetch_one=True)
        return result[0] > 0 if result else False
    
    def create_indexes_if_not_exist(self):
        """Crea indici ottimizzati se non esistono"""
        indexes = [
            {
                'table': 'radiocontrol',
                'name': 'idx_radiocontrol_timestamp',
                'columns': ['timestamp'],
                'type': 'INDEX'
            },
            {
                'table': 'radiocontrol',
                'name': 'idx_radiocontrol_punch_time',
                'columns': ['punch_time'],
                'type': 'INDEX'
            },
            {
                'table': 'radiocontrol',
                'name': 'idx_radiocontrol_sent_internet',
                'columns': ['sent_internet'],
                'type': 'INDEX'
            },
            {
                'table': 'punches',
                'name': 'idx_punches_punch_time',
                'columns': ['punch_time'],
                'type': 'INDEX'
            },
            {
                'table': 'punches',
                'name': 'idx_punches_timestamp',
                'columns': ['timestamp'],
                'type': 'INDEX'
            },
            {
                'table': 'meshtastic_log',
                'name': 'idx_meshtastic_log_event_time',
                'columns': ['event_time'],
                'type': 'INDEX'
            },
            {
                'table': 'meshtastic_log',
                'name': 'idx_meshtastic_log_direction_type',
                'columns': ['direction', 'msg_type'],
                'type': 'INDEX'
            },
            {
                'table': 'messaggi',
                'name': 'idx_messaggi_data_ora',
                'columns': ['data_ora'],
                'type': 'INDEX'
            },
            {
                'table': 'nodes',
                'name': 'idx_nodes_last_signal',
                'columns': ['last_signal'],
                'type': 'INDEX'
            }
        ]
        
        for index in indexes:
            try:
                if self.check_table_exists(index['table']):
                    # Verifica se l'indice esiste già
                    check_query = """
                    SELECT COUNT(*) as count
                    FROM information_schema.statistics 
                    WHERE table_schema = DATABASE() 
                    AND table_name = %s 
                    AND index_name = %s
                    """
                    result = self.execute_query(check_query, (index['table'], index['name']), fetch_one=True)
                    
                    if result[0] == 0:
                        # Crea l'indice
                        columns_str = ', '.join(index['columns'])
                        create_query = f"CREATE {index['type']} {index['name']} ON {index['table']} ({columns_str})"
                        self.execute_query(create_query)
                        self.logger.info(f"Indice creato: {index['name']} su {index['table']}")
                    else:
                        self.logger.debug(f"Indice già esistente: {index['name']} su {index['table']}")
                        
            except Exception as e:
                self.logger.warning(f"Errore creazione indice {index['name']}: {e}")
    
    def get_pool_status(self) -> Dict[str, Any]:
        """Restituisce lo stato del pool di connessioni"""
        if not self.pool:
            return {'status': 'not_initialized'}
        
        try:
            return {
                'pool_name': self.pool.pool_name,
                'pool_size': self.pool.pool_size,
                'connections_in_use': len([c for c in self.pool._cnx_queue._queue if c.is_connected()]),
                'status': 'healthy'
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Esegue un health check completo del database"""
        health_status = {
            'database': 'unknown',
            'pool': 'unknown',
            'connection_test': 'unknown',
            'timestamp': time.time()
        }
        
        try:
            # Test pool
            pool_status = self.get_pool_status()
            health_status['pool'] = 'healthy' if pool_status.get('status') == 'healthy' else 'unhealthy'
            
            # Test connessione
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1, NOW()")
                    result = cursor.fetchone()
                    if result[0] == 1:
                        health_status['connection_test'] = 'healthy'
                        health_status['database_time'] = result[1]
                    else:
                        health_status['connection_test'] = 'unhealthy'
            
            health_status['database'] = 'healthy'
            
        except Exception as e:
            health_status['database'] = 'unhealthy'
            health_status['error'] = str(e)
            self.logger.error(f"Health check fallito: {e}")
        
        return health_status
    
    def cleanup(self):
        """Pulisce le risorse del database manager"""
        try:
            if self.pool:
                # Chiudi tutte le connessioni nel pool
                while not self.pool._cnx_queue.empty():
                    try:
                        conn = self.pool._cnx_queue.get_nowait()
                        if conn.is_connected():
                            conn.close()
                    except:
                        pass
                self.logger.info("Pool database chiuso")
        except Exception as e:
            self.logger.error(f"Errore cleanup database: {e}")


# Utility functions per operazioni comuni
class DatabaseOperations:
    """Operazioni database specifiche per OriBruniRadioControls"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.logger = logging.getLogger('DatabaseOperations')
    
    def insert_radiocontrol_punch(self, control: int, card_number: int, punch_time: str, 
                                 raw_punch_data: str, timestamp: str) -> Optional[int]:
        """Inserisce una punzonatura nella tabella radiocontrol"""
        data = {
            'control': control,
            'card_number': card_number,
            'punch_time': punch_time,
            'raw_punch_data': raw_punch_data,
            'timestamp': timestamp,
            'sent_internet': 0
        }
        return self.db.insert_record('radiocontrol', data)
    
    def get_unsent_records(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Ottiene record non ancora inviati online"""
        query = """
        SELECT * FROM radiocontrol 
        WHERE sent_internet = 0 
        ORDER BY id ASC 
        LIMIT %s
        """
        return self.db.execute_query(query, (limit,), fetch_all=True, dictionary=True)
    
    def mark_record_as_sent(self, record_id: int) -> bool:
        """Marca un record come inviato"""
        try:
            rows_affected = self.db.update_record(
                'radiocontrol',
                {'sent_internet': 1},
                'id = %s',
                (record_id,)
            )
            return rows_affected > 0
        except Exception as e:
            self.logger.error(f"Errore marcatura record {record_id}: {e}")
            return False
    
    def log_meshtastic_message(self, direction: str, msg_type: int, payload: str, 
                              peer_id: str = '', node_name: str = '') -> Optional[int]:
        """Inserisce un log Meshtastic"""
        data = {
            'direction': direction,
            'msg_type': msg_type,
            'event_time': 'NOW()',
            'node_name': node_name,
            'peer_id': peer_id,
            'payload': payload
        }
        return self.db.insert_record('meshtastic_log', data)
    
    def get_device_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Ottiene nome e pkey del dispositivo"""
        query = """
        SELECT nome, valore 
        FROM costanti 
        WHERE nome IN ('nome', 'pkey') 
        ORDER BY nome
        """
        try:
            rows = self.db.execute_query(query, fetch_all=True)
            if len(rows) == 2:
                creds = {row[0]: row[1] for row in rows}
                return creds.get('nome'), creds.get('pkey')
            return None, None
        except Exception as e:
            self.logger.error(f"Errore lettura credenziali: {e}")
            return None, None
    
    def log_event(self, nome: str, errore: str, descrizione: str) -> Optional[int]:
        """Inserisce un evento nel log"""
        data = {
            'nome': nome,
            'errore': errore,
            'descrizione': descrizione,
            'timestamp': 'NOW()'
        }
        return self.db.insert_record('log', data)


if __name__ == '__main__':
    # Test del database manager
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Crea config manager
        config = ConfigManager()
        
        # Crea database manager
        db_manager = DatabaseManager(config)
        
        # Test health check
        health = db_manager.health_check()
        print(f"Health check: {health}")
        
        # Test operazioni
        db_ops = DatabaseOperations(db_manager)
        
        # Test lettura credenziali
        nome, pkey = db_ops.get_device_credentials()
        print(f"Credenziali dispositivo: nome={nome}, pkey={pkey}")
        
        # Test creazione indici
        db_manager.create_indexes_if_not_exist()
        
        print("Test database manager completato con successo")
        
    except Exception as e:
        print(f"Errore test database manager: {e}")
    finally:
        if 'db_manager' in locals():
            db_manager.cleanup()

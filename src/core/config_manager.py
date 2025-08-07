#!/usr/bin/env python3
"""
Config Manager per OriBruniRadioControls
Gestisce configurazioni sicure con crittografia password e validazione
"""

import os
import json
import logging
import configparser
from typing import Dict, Any, Optional
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class ConfigManager:
    """Gestione sicura delle configurazioni con crittografia password"""
    
    def __init__(self, config_path: str = 'config.ini'):
        self.config_path = Path(config_path)
        self.config = configparser.ConfigParser()
        self._cipher = None
        self._setup_encryption()
        self.load_config()
    
    def _setup_encryption(self):
        """Configura la crittografia per le password"""
        # Usa variabile d'ambiente o genera chiave
        key_env = os.environ.get('ORIBRUNI_ENCRYPTION_KEY')
        if key_env:
            self._cipher = Fernet(key_env.encode())
        else:
            # Genera chiave da password master
            master_password = os.environ.get('ORIBRUNI_MASTER_PASSWORD', 'default_change_me')
            salt = b'oribruni_salt_2025'  # In produzione, usa salt random salvato
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
            self._cipher = Fernet(key)
    
    def encrypt_password(self, password: str) -> str:
        """Cripta una password"""
        return self._cipher.encrypt(password.encode()).decode()
    
    def decrypt_password(self, encrypted_password: str) -> str:
        """Decripta una password"""
        try:
            return self._cipher.decrypt(encrypted_password.encode()).decode()
        except Exception as e:
            logging.error(f"Errore decrittazione password: {e}")
            return encrypted_password  # Fallback per password non crittate
    
    def load_config(self):
        """Carica configurazione da file"""
        if not self.config_path.exists():
            self._create_default_config()
        
        self.config.read(self.config_path)
        self._validate_config()
    
    def _create_default_config(self):
        """Crea configurazione di default"""
        default_config = {
            'SERIAL': {
                'port': '/dev/ttyUSB0',
                'baudrate': '38400',
                'poll_serial_ms': '10',
                'sportident_port': 'auto'
            },
            'DATABASE': {
                'user': 'root',
                'password_encrypted': 'false',
                'password': 'CHANGE_ME',
                'host': 'localhost',
                'database': 'OriBruniRadioControls',
                'port': '3306',
                'autocommit': 'true',
                'pool_size': '5',
                'pool_name': 'oribruni_pool'
            },
            'REMOTE': {
                'url': 'https://orienteering.services/radiocontrol/receive_data.php',
                'max_retries': '3',
                'backoff_factor': '0.5',
                'timeout': '10',
                'verify_ssl': 'true'
            },
            'LOGGING': {
                'level': 'INFO',
                'max_size_mb': '10',
                'backup_count': '5',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'EXECUTION': {
                'max_workers': '3',
                'watchdog_interval': '60',
                'shutdown_timeout': '30'
            },
            'RASPBERRY': {
                'optimize_power': 'true',
                'cpu_limit': '80',
                'network_timeout': '30',
                'keep_alive_interval': '300',
                'gpio_cleanup': 'true'
            },
            'MESHTASTIC': {
                'port': 'auto',
                'baudrate': '115200',
                'topic': 'punch_data',
                'ack': 'false',
                'neigh_info_interval': '30',
                'http_host': 'localhost',
                'http_port': '8000',
                'reconnect_interval': '10',
                'max_reconnect_attempts': '5'
            },
            'SECURITY': {
                'enable_encryption': 'true',
                'api_key_required': 'false',
                'rate_limit_enabled': 'true',
                'max_requests_per_minute': '100'
            },
            'MONITORING': {
                'enable_health_checks': 'true',
                'health_check_interval': '30',
                'metrics_enabled': 'false',
                'prometheus_port': '9090'
            }
        }
        
        # Crea il file di configurazione
        for section, options in default_config.items():
            self.config.add_section(section)
            for key, value in options.items():
                self.config.set(section, key, value)
        
        self.save_config()
        logging.warning(f"Configurazione di default creata in {self.config_path}")
        logging.warning("IMPORTANTE: Modifica le password e le configurazioni prima dell'uso in produzione!")
    
    def _validate_config(self):
        """Valida la configurazione caricata"""
        required_sections = ['SERIAL', 'DATABASE', 'REMOTE', 'LOGGING']
        
        for section in required_sections:
            if not self.config.has_section(section):
                raise ValueError(f"Sezione mancante nella configurazione: {section}")
        
        # Valida configurazioni critiche
        if self.config.get('DATABASE', 'password') == 'CHANGE_ME':
            logging.error("Password database non configurata! Cambia 'CHANGE_ME' in config.ini")
            raise ValueError("Password database non sicura")
        
        # Valida porte numeriche
        try:
            int(self.config.get('DATABASE', 'port'))
            int(self.config.get('MESHTASTIC', 'http_port'))
        except ValueError as e:
            raise ValueError(f"Porta non valida nella configurazione: {e}")
    
    def get_database_config(self) -> Dict[str, Any]:
        """Restituisce configurazione database con password decriptata"""
        db_config = dict(self.config['DATABASE'])
        
        # Decripta password se necessario
        if db_config.get('password_encrypted', 'false').lower() == 'true':
            db_config['password'] = self.decrypt_password(db_config['password'])
        
        # Converte tipi
        db_config['port'] = int(db_config['port'])
        db_config['autocommit'] = db_config.get('autocommit', 'true').lower() == 'true'
        
        # Rimuove campi non necessari per mysql.connector
        db_config.pop('password_encrypted', None)
        db_config.pop('pool_size', None)
        db_config.pop('pool_name', None)
        
        return db_config
    
    def get_section(self, section: str) -> Dict[str, str]:
        """Restituisce una sezione della configurazione"""
        if not self.config.has_section(section):
            raise ValueError(f"Sezione non trovata: {section}")
        return dict(self.config[section])
    
    def get(self, section: str, key: str, fallback: Any = None) -> str:
        """Ottiene un valore dalla configurazione"""
        return self.config.get(section, key, fallback=fallback)
    
    def getint(self, section: str, key: str, fallback: int = None) -> int:
        """Ottiene un valore intero dalla configurazione"""
        return self.config.getint(section, key, fallback=fallback)
    
    def getboolean(self, section: str, key: str, fallback: bool = None) -> bool:
        """Ottiene un valore booleano dalla configurazione"""
        return self.config.getboolean(section, key, fallback=fallback)
    
    def set_encrypted_password(self, section: str, password: str):
        """Imposta una password crittata nella configurazione"""
        encrypted = self.encrypt_password(password)
        self.config.set(section, 'password', encrypted)
        self.config.set(section, 'password_encrypted', 'true')
        self.save_config()
    
    def save_config(self):
        """Salva la configurazione su file"""
        with open(self.config_path, 'w') as f:
            self.config.write(f)
    
    def reload_config(self):
        """Ricarica la configurazione da file"""
        self.load_config()
        logging.info("Configurazione ricaricata")
    
    def export_config_template(self, output_path: str = 'config.template.ini'):
        """Esporta un template di configurazione senza password"""
        template_config = configparser.ConfigParser()
        
        for section_name in self.config.sections():
            template_config.add_section(section_name)
            for key, value in self.config[section_name].items():
                if 'password' in key.lower():
                    template_config.set(section_name, key, 'CHANGE_ME')
                else:
                    template_config.set(section_name, key, value)
        
        with open(output_path, 'w') as f:
            template_config.write(f)
        
        logging.info(f"Template configurazione esportato in {output_path}")


# Utility per migrazione configurazioni esistenti
def migrate_existing_config(old_config_path: str = 'config.ini', backup: bool = True):
    """Migra una configurazione esistente al nuovo formato sicuro"""
    if not Path(old_config_path).exists():
        logging.error(f"File configurazione non trovato: {old_config_path}")
        return False
    
    # Backup del file esistente
    if backup:
        backup_path = f"{old_config_path}.backup"
        Path(old_config_path).rename(backup_path)
        logging.info(f"Backup creato: {backup_path}")
    
    # Carica vecchia configurazione
    old_config = configparser.ConfigParser()
    old_config.read(old_config_path if not backup else f"{old_config_path}.backup")
    
    # Crea nuovo config manager
    config_manager = ConfigManager(old_config_path)
    
    # Migra le password
    if old_config.has_section('DATABASE') and old_config.has_option('DATABASE', 'password'):
        old_password = old_config.get('DATABASE', 'password')
        if old_password != 'CHANGE_ME':
            config_manager.set_encrypted_password('DATABASE', old_password)
            logging.info("Password database migrata e crittata")
    
    logging.info("Migrazione configurazione completata")
    return True


if __name__ == '__main__':
    # Test del config manager
    logging.basicConfig(level=logging.INFO)
    
    # Crea config manager
    config = ConfigManager()
    
    # Test crittografia password
    test_password = "test_password_123"
    encrypted = config.encrypt_password(test_password)
    decrypted = config.decrypt_password(encrypted)
    
    print(f"Password originale: {test_password}")
    print(f"Password crittata: {encrypted}")
    print(f"Password decrittata: {decrypted}")
    print(f"Test crittografia: {'OK' if test_password == decrypted else 'FAILED'}")
    
    # Test configurazione database
    try:
        db_config = config.get_database_config()
        print(f"Configurazione database: {db_config}")
    except Exception as e:
        print(f"Errore configurazione database: {e}")

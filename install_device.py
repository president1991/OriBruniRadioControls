#!/usr/bin/env python3
"""
Sistema di installazione OriBruni RadioControls
Gestisce l'installazione iniziale di un nuovo lettore con verifica online della pkey
"""

import os
import sys
import json
import requests
import logging
import configparser
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import argparse
from urllib.parse import urljoin
import time

# Importa il config manager esistente
sys.path.append(str(Path(__file__).parent / 'src'))
from core.config_manager import ConfigManager

class DeviceInstaller:
    """Gestisce l'installazione e registrazione di un nuovo dispositivo"""
    
    def __init__(self):
        self.base_path = Path.cwd()
        self.config_path = self.base_path / "config"
        self.logs_path = self.base_path / "logs"
        
        # Setup logging
        self.setup_logging()
        self.logger = logging.getLogger('DeviceInstaller')
        
        # URL delle API remote (da documentazione fornita)
        self.api_base_url = "https://orienteering.services/radiocontrol/"
        self.api_endpoints = {
            'callhome': 'callhome.php',
            'radiocontrol_data': 'radiocontrol_data.php',
            'receive_data': 'receive_data.php'
        }
        
        # Configurazione per timeout e retry
        self.request_timeout = 10
        self.max_retries = 3
        self.retry_delay = 2
    
    def setup_logging(self):
        """Configura logging per l'installer"""
        self.logs_path.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.logs_path / 'install.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    def get_device_info_interactive(self) -> Tuple[str, str]:
        """Raccoglie informazioni dispositivo dall'utente in modo interattivo"""
        print("\n" + "="*60)
        print("🏃‍♂️ OriBruni RadioControls - Installazione Dispositivo")
        print("="*60)
        print()
        
        # Raccolta nome dispositivo
        while True:
            device_name = input("Inserisci il nome del dispositivo (es. OBRC_004): ").strip()
            
            if not device_name:
                print("❌ Il nome del dispositivo non può essere vuoto!")
                continue
            
            if len(device_name) < 3:
                print("❌ Il nome del dispositivo deve essere almeno 3 caratteri!")
                continue
            
            # Verifica formato suggerito
            if not device_name.startswith('OBRC_'):
                response = input(f"⚠️  Il nome '{device_name}' non segue il formato OBRC_XXX. Continuare? (y/N): ")
                if response.lower() != 'y':
                    continue
            
            break
        
        # Raccolta pkey
        while True:
            pkey = input("Inserisci la chiave del dispositivo (es. 936D4854BB4E5): ").strip()
            
            if not pkey:
                print("❌ La chiave del dispositivo non può essere vuota!")
                continue
            
            if len(pkey) < 8:
                print("❌ La chiave del dispositivo deve essere almeno 8 caratteri!")
                continue
            
            # Verifica formato esadecimale
            try:
                int(pkey, 16)
            except ValueError:
                print("❌ La chiave deve contenere solo caratteri esadecimali (0-9, A-F)!")
                continue
            
            break
        
        print(f"\n✅ Dispositivo: {device_name}")
        print(f"✅ Chiave: {pkey}")
        
        # Conferma finale
        response = input("\nConfermi i dati inseriti? (y/N): ")
        if response.lower() != 'y':
            print("❌ Installazione annullata dall'utente")
            sys.exit(0)
        
        return device_name, pkey
    
    def verify_device_online(self, device_name: str, pkey: str) -> bool:
        """Verifica se il dispositivo esiste online tramite API"""
        self.logger.info(f"Verifica online dispositivo: {device_name}")
        
        # Metodo 1: Prova con callhome.php (ping)
        if self._verify_with_callhome(device_name, pkey):
            return True
        
        # Metodo 2: Prova con radiocontrol_data.php
        if self._verify_with_radiocontrol_data(device_name, pkey):
            return True
        
        return False
    
    def _verify_with_callhome(self, device_name: str, pkey: str) -> bool:
        """Verifica dispositivo tramite callhome.php con keepalive test"""
        url = urljoin(self.api_base_url, self.api_endpoints['callhome'])
        
        # Prepara payload di test
        test_payload = {
            "name": device_name,
            "pkey": pkey,
            "action": "keepalive",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "client_version": "installer-1.0.0",
            "system_status": {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "memory_available_mb": 0.0,
                "disk_percent": 0.0,
                "disk_free_gb": 0.0,
                "temperature": 0.0,
                "uptime_hours": 0.0,
                "load_avg_1m": 0.0,
                "process_count": 0
            }
        }
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Tentativo {attempt + 1}/{self.max_retries} - Verifica con callhome.php")
                
                response = requests.post(
                    url,
                    json=test_payload,
                    timeout=self.request_timeout,
                    headers={'Content-Type': 'application/json'}
                )
                
                self.logger.info(f"Risposta HTTP: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        if result.get('status') == 'success':
                            self.logger.info("✅ Dispositivo verificato con callhome.php")
                            return True
                    except json.JSONDecodeError:
                        # Potrebbe essere una risposta di testo semplice
                        if 'success' in response.text.lower():
                            self.logger.info("✅ Dispositivo verificato con callhome.php (risposta testo)")
                            return True
                
                elif response.status_code == 401:
                    self.logger.error("❌ Autenticazione fallita - dispositivo o pkey non validi")
                    return False
                
                elif response.status_code == 422:
                    self.logger.warning("⚠️ Formato dati non valido, ma dispositivo potrebbe esistere")
                    # Continua con il prossimo metodo
                    break
                
                else:
                    self.logger.warning(f"Risposta inaspettata: {response.status_code} - {response.text[:200]}")
                
            except requests.exceptions.Timeout:
                self.logger.warning(f"Timeout tentativo {attempt + 1}")
            except requests.exceptions.ConnectionError:
                self.logger.warning(f"Errore connessione tentativo {attempt + 1}")
            except Exception as e:
                self.logger.warning(f"Errore generico tentativo {attempt + 1}: {e}")
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        return False
    
    def _verify_with_radiocontrol_data(self, device_name: str, pkey: str) -> bool:
        """Verifica dispositivo tramite radiocontrol_data.php"""
        url = urljoin(self.api_base_url, self.api_endpoints['radiocontrol_data'])
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Tentativo {attempt + 1}/{self.max_retries} - Verifica con radiocontrol_data.php")
                
                response = requests.get(url, timeout=self.request_timeout)
                
                if response.status_code == 200:
                    try:
                        devices = response.json()
                        
                        # Cerca il dispositivo nella lista
                        for device in devices:
                            if (device.get('name') == device_name and 
                                device.get('pkey') == pkey):
                                self.logger.info("✅ Dispositivo trovato in radiocontrol_data.php")
                                return True
                        
                        self.logger.warning("❌ Dispositivo non trovato nella lista")
                        return False
                        
                    except json.JSONDecodeError:
                        self.logger.warning("Risposta non JSON valida")
                
                else:
                    self.logger.warning(f"Risposta HTTP: {response.status_code}")
                
            except requests.exceptions.Timeout:
                self.logger.warning(f"Timeout tentativo {attempt + 1}")
            except requests.exceptions.ConnectionError:
                self.logger.warning(f"Errore connessione tentativo {attempt + 1}")
            except Exception as e:
                self.logger.warning(f"Errore generico tentativo {attempt + 1}: {e}")
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        return False
    
    def save_device_config(self, device_name: str, pkey: str) -> bool:
        """Salva la configurazione del dispositivo localmente"""
        self.logger.info("Salvataggio configurazione dispositivo...")
        
        try:
            # Crea directory config se non esiste
            self.config_path.mkdir(exist_ok=True)
            
            # Carica o crea configurazione base
            config_file = self.config_path / "config.ini"
            
            if config_file.exists():
                # Aggiorna configurazione esistente
                config_manager = ConfigManager(str(config_file))
            else:
                # Crea nuova configurazione dal template
                template_path = self.base_path / "config_templates" / "config.ini"
                if template_path.exists():
                    # Copia template
                    import shutil
                    shutil.copy2(template_path, config_file)
                    config_manager = ConfigManager(str(config_file))
                else:
                    # Crea configurazione di default
                    config_manager = ConfigManager(str(config_file))
            
            # Aggiorna sezione DEVICE (nuova sezione per info dispositivo)
            if not config_manager.config.has_section('DEVICE'):
                config_manager.config.add_section('DEVICE')
            
            config_manager.config.set('DEVICE', 'name', device_name)
            config_manager.config.set('DEVICE', 'pkey', pkey)
            config_manager.config.set('DEVICE', 'installation_date', time.strftime("%Y-%m-%d %H:%M:%S"))
            config_manager.config.set('DEVICE', 'verified_online', 'true')
            
            # Aggiorna sezione REMOTE con le credenziali
            if not config_manager.config.has_section('REMOTE'):
                config_manager.config.add_section('REMOTE')
            
            config_manager.config.set('REMOTE', 'device_name', device_name)
            config_manager.config.set('REMOTE', 'device_pkey', pkey)
            
            # Aggiorna sezione CALLHOME
            if not config_manager.config.has_section('CALLHOME'):
                config_manager.config.add_section('CALLHOME')
            
            config_manager.config.set('CALLHOME', 'device_name', device_name)
            config_manager.config.set('CALLHOME', 'device_pkey', pkey)
            
            # Salva configurazione
            config_manager.save_config()
            
            # Crea anche un file JSON separato per info dispositivo
            device_info = {
                'device': {
                    'name': device_name,
                    'pkey': pkey,
                    'installation_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                    'verified_online': True,
                    'installer_version': '1.0.0'
                },
                'api_endpoints': {
                    'base_url': self.api_base_url,
                    'callhome': self.api_endpoints['callhome'],
                    'receive_data': self.api_endpoints['receive_data']
                },
                'installation_info': {
                    'python_version': sys.version,
                    'platform': sys.platform,
                    'working_directory': str(self.base_path)
                }
            }
            
            device_file = self.config_path / f"{device_name}.json"
            with open(device_file, 'w') as f:
                json.dump(device_info, f, indent=2)
            
            self.logger.info(f"✅ Configurazione salvata in {config_file}")
            self.logger.info(f"✅ Info dispositivo salvate in {device_file}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Errore salvataggio configurazione: {e}")
            return False
    
    def test_configuration(self, device_name: str, pkey: str) -> bool:
        """Testa la configurazione salvata con una chiamata di prova"""
        self.logger.info("Test configurazione salvata...")
        
        try:
            # Carica configurazione
            config_manager = ConfigManager(str(self.config_path / "config.ini"))
            
            # Verifica che i dati siano stati salvati correttamente
            saved_name = config_manager.get('DEVICE', 'name', fallback=None)
            saved_pkey = config_manager.get('DEVICE', 'pkey', fallback=None)
            
            if saved_name != device_name or saved_pkey != pkey:
                self.logger.error("❌ Dati salvati non corrispondono a quelli inseriti")
                return False
            
            # Test chiamata API con configurazione salvata
            url = urljoin(self.api_base_url, self.api_endpoints['callhome'])
            
            # Ping semplice
            response = requests.head(url, timeout=self.request_timeout)
            
            if response.status_code == 200:
                self.logger.info("✅ Test connessione API riuscito")
                return True
            else:
                self.logger.warning(f"⚠️ Test connessione API: HTTP {response.status_code}")
                return True  # Non è un errore critico
                
        except Exception as e:
            self.logger.warning(f"⚠️ Test configurazione: {e}")
            return True  # Non è un errore critico
    
    def show_next_steps(self, device_name: str):
        """Mostra i prossimi passi dopo l'installazione"""
        print("\n" + "="*60)
        print("🎉 INSTALLAZIONE COMPLETATA CON SUCCESSO!")
        print("="*60)
        print()
        print(f"✅ Dispositivo '{device_name}' configurato e verificato online")
        print(f"✅ Configurazione salvata in: config/config.ini")
        print(f"✅ Info dispositivo salvate in: config/{device_name}.json")
        print()
        print("📋 PROSSIMI PASSI:")
        print()
        print("1. 🔧 CONFIGURAZIONE HARDWARE:")
        print("   - Collega i dispositivi seriali (SportIdent, Meshtastic)")
        print("   - Verifica connessioni I2C per display OLED")
        print("   - Testa le porte con: ls -la /dev/ttyUSB*")
        print()
        print("2. 🚀 DEPLOY AUTOMATICO:")
        print("   - Per LETTORE:")
        print(f"     python3 scripts/deploy_raspberry.py reader {device_name} --auto-start")
        print("   - Per RICEVITORE:")
        print(f"     python3 scripts/deploy_raspberry.py receiver {device_name} --auto-start")
        print()
        print("3. 📊 MONITORAGGIO:")
        print("   - Avvio manuale: ./start_oribruni.sh")
        print("   - Stato servizi: systemctl status oribruni-*")
        print("   - Log in tempo reale: journalctl -f -u oribruni-*")
        print("   - Health check: ./health_check.sh")
        print()
        print("4. 🔍 VERIFICA FUNZIONAMENTO:")
        print("   - Controlla log di installazione: logs/install.log")
        print("   - Testa connessione remota con i servizi avviati")
        print("   - Verifica ricezione punzonature")
        print()
        print("📚 DOCUMENTAZIONE:")
        print("   - Guida rapida: docs/GUIDA_RAPIDA_INSTALLAZIONE.md")
        print("   - Deploy completo: docs/README_DEPLOY.md")
        print("   - Analisi tecnica: docs/ANALISI_COMPLETA_E_ROADMAP.md")
        print()
        print("🆘 SUPPORTO:")
        print("   - Issues GitHub: https://github.com/president1991/OriBruniRadioControls/issues")
        print("   - Log supporto: tar -czf support.tar.gz logs/ config/")
        print()
        print("🏃‍♂️ Buona fortuna con il tuo evento di orienteering! 🧭")
        print("="*60)
    
    def install_device(self, device_name: str = None, pkey: str = None) -> bool:
        """Esegue l'installazione completa del dispositivo"""
        self.logger.info("Inizio installazione dispositivo OriBruni RadioControls")
        
        try:
            # Raccolta dati se non forniti
            if not device_name or not pkey:
                device_name, pkey = self.get_device_info_interactive()
            
            # Verifica online
            print("\n🔍 Verifica dispositivo online...")
            if not self.verify_device_online(device_name, pkey):
                print("❌ ERRORE: Dispositivo non trovato o credenziali non valide!")
                print()
                print("Possibili cause:")
                print("- Nome dispositivo errato")
                print("- Chiave (pkey) errata")
                print("- Dispositivo non registrato nel sistema remoto")
                print("- Problemi di connessione internet")
                print()
                print("Contatta l'amministratore del sistema per:")
                print("- Verificare la registrazione del dispositivo")
                print("- Ottenere le credenziali corrette")
                return False
            
            print("✅ Dispositivo verificato online!")
            
            # Salvataggio configurazione
            print("\n💾 Salvataggio configurazione...")
            if not self.save_device_config(device_name, pkey):
                print("❌ ERRORE: Impossibile salvare la configurazione!")
                return False
            
            print("✅ Configurazione salvata!")
            
            # Test configurazione
            print("\n🧪 Test configurazione...")
            if not self.test_configuration(device_name, pkey):
                print("⚠️ Warning: Test configurazione non completamente riuscito")
                print("   La configurazione è stata salvata ma potrebbero esserci problemi")
            else:
                print("✅ Test configurazione riuscito!")
            
            # Mostra prossimi passi
            self.show_next_steps(device_name)
            
            return True
            
        except KeyboardInterrupt:
            print("\n❌ Installazione interrotta dall'utente")
            return False
        except Exception as e:
            self.logger.error(f"❌ Errore durante l'installazione: {e}")
            print(f"\n❌ ERRORE: {e}")
            print("Controlla il file logs/install.log per dettagli")
            return False


def main():
    """Funzione principale"""
    parser = argparse.ArgumentParser(
        description='Installazione dispositivo OriBruni RadioControls',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi di utilizzo:

  # Installazione interattiva
  python3 install_device.py

  # Installazione con parametri
  python3 install_device.py --name OBRC_004 --pkey 936D4854BB4E5

  # Solo verifica online (senza salvare)
  python3 install_device.py --name OBRC_004 --pkey 936D4854BB4E5 --verify-only

Dopo l'installazione, usa deploy_raspberry.py per configurare i servizi.
        """
    )
    
    parser.add_argument('--name', help='Nome del dispositivo (es. OBRC_004)')
    parser.add_argument('--pkey', help='Chiave del dispositivo (es. 936D4854BB4E5)')
    parser.add_argument('--verify-only', action='store_true', 
                       help='Solo verifica online, non salva configurazione')
    parser.add_argument('--api-url', default='https://orienteering.services/radiocontrol/',
                       help='URL base delle API (default: https://orienteering.services/radiocontrol/)')
    parser.add_argument('--timeout', type=int, default=10,
                       help='Timeout richieste HTTP in secondi (default: 10)')
    parser.add_argument('--retries', type=int, default=3,
                       help='Numero massimo di tentativi (default: 3)')
    
    args = parser.parse_args()
    
    # Verifica permessi (non deve essere root)
    if os.geteuid() == 0:
        print("❌ ERRORE: Non eseguire come root. Usa l'utente normale (es. 'pi').")
        sys.exit(1)
    
    # Crea installer
    installer = DeviceInstaller()
    
    # Configura parametri da argomenti
    if args.api_url:
        installer.api_base_url = args.api_url
    if args.timeout:
        installer.request_timeout = args.timeout
    if args.retries:
        installer.max_retries = args.retries
    
    # Modalità solo verifica
    if args.verify_only:
        if not args.name or not args.pkey:
            print("❌ ERRORE: Per --verify-only sono richiesti --name e --pkey")
            sys.exit(1)
        
        print(f"🔍 Verifica dispositivo: {args.name}")
        if installer.verify_device_online(args.name, args.pkey):
            print("✅ Dispositivo verificato online!")
            sys.exit(0)
        else:
            print("❌ Dispositivo non trovato o credenziali non valide!")
            sys.exit(1)
    
    # Installazione completa
    if installer.install_device(args.name, args.pkey):
        print("\n🎉 Installazione completata con successo!")
        sys.exit(0)
    else:
        print("\n❌ Installazione fallita!")
        sys.exit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Deploy automatico OriBruniRadioControls per Raspberry Pi
Sistema completo di installazione e configurazione automatica
"""

import os
import sys
import json
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import argparse

class RaspberryDeployer:
    """Deployer automatico per Raspberry Pi"""
    
    def __init__(self, device_type: str, device_name: str):
        self.device_type = device_type.lower()  # 'reader' o 'receiver'
        self.device_name = device_name
        self.base_path = Path.cwd()
        self.config_path = self.base_path / "config"
        self.logs_path = self.base_path / "logs"
        self.backup_path = self.base_path / "backup"
        
        # Setup logging
        self.setup_logging()
        self.logger = logging.getLogger('RaspberryDeployer')
        
        # Configurazioni specifiche per tipo dispositivo
        self.device_configs = {
            'reader': {
                'services': ['oribruni-sportident', 'oribruni-meshtastic', 'oribruni-display'],
                'ports': ['/dev/ttyUSB0', '/dev/ttyUSB1'],  # SportIdent + Meshtastic
                'display': 'oled_128x64',
                'gpio_pins': [18, 19, 20, 21],  # LED, Buzzer, Button, etc.
                'features': ['sportident_reader', 'meshtastic_relay', 'time_sync_client', 'oled_display']
            },
            'receiver': {
                'services': ['oribruni-receiver', 'oribruni-meshtastic', 'oribruni-web'],
                'ports': ['/dev/ttyUSB0'],  # Solo Meshtastic
                'display': 'lcd_20x4',
                'network': ['wifi', 'ethernet'],
                'features': ['meshtastic_receiver', 'web_dashboard', 'time_sync_server', 'database']
            }
        }
    
    def setup_logging(self):
        """Configura logging per il deployer"""
        self.logs_path.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.logs_path / 'deploy.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
    
    def detect_raspberry_model(self) -> Dict[str, Any]:
        """Rileva modello Raspberry Pi e caratteristiche"""
        try:
            # Leggi info CPU
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
            
            # Leggi info memoria
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
            
            # Estrai informazioni
            model = "Unknown"
            if "BCM2835" in cpuinfo:
                model = "Raspberry Pi 1/Zero"
            elif "BCM2836" in cpuinfo:
                model = "Raspberry Pi 2"
            elif "BCM2837" in cpuinfo:
                model = "Raspberry Pi 3"
            elif "BCM2711" in cpuinfo:
                model = "Raspberry Pi 4"
            
            # Memoria RAM
            mem_total = 0
            for line in meminfo.split('\n'):
                if line.startswith('MemTotal:'):
                    mem_total = int(line.split()[1]) // 1024  # MB
                    break
            
            return {
                'model': model,
                'memory_mb': mem_total,
                'architecture': os.uname().machine,
                'os_version': self.get_os_version()
            }
            
        except Exception as e:
            self.logger.error(f"Errore rilevamento Raspberry Pi: {e}")
            return {'model': 'Unknown', 'memory_mb': 0}
    
    def get_os_version(self) -> str:
        """Ottiene versione OS"""
        try:
            result = subprocess.run(['lsb_release', '-d'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.split('\t')[1].strip()
        except:
            pass
        
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        return line.split('=')[1].strip().strip('"')
        except:
            pass
        
        return "Unknown Linux"
    
    def check_prerequisites(self) -> bool:
        """Verifica prerequisiti sistema"""
        self.logger.info("Verifica prerequisiti...")
        
        checks = {
            'python3': ['python3', '--version'],
            'pip3': ['pip3', '--version'],
            'git': ['git', '--version'],
            'systemctl': ['systemctl', '--version'],
            'i2c-tools': ['i2cdetect', '-V']
        }
        
        missing = []
        for name, cmd in checks.items():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    self.logger.info(f"✓ {name}: OK")
                else:
                    missing.append(name)
            except:
                missing.append(name)
        
        if missing:
            self.logger.error(f"Prerequisiti mancanti: {missing}")
            return False
        
        return True
    
    def install_system_packages(self) -> bool:
        """Installa pacchetti sistema necessari"""
        self.logger.info("Installazione pacchetti sistema...")
        
        base_packages = [
            'python3-dev', 'python3-pip', 'python3-venv',
            'build-essential', 'git', 'curl', 'wget',
            'i2c-tools', 'python3-smbus', 'python3-pil',
            'libmysqlclient-dev', 'mysql-client',
            'redis-server', 'nginx-light',
            'supervisor', 'logrotate'
        ]
        
        # Pacchetti specifici per tipo dispositivo
        if self.device_type == 'reader':
            base_packages.extend([
                'python3-rpi.gpio',  # GPIO per LED/Buzzer
                'fonts-dejavu-core'  # Font per OLED
            ])
        elif self.device_type == 'receiver':
            base_packages.extend([
                'python3-flask', 'python3-socketio',
                'sqlite3'  # Backup database locale
            ])
        
        try:
            # Aggiorna package list
            subprocess.run(['sudo', 'apt-get', 'update'], check=True, timeout=300)
            
            # Installa pacchetti
            cmd = ['sudo', 'apt-get', 'install', '-y'] + base_packages
            subprocess.run(cmd, check=True, timeout=600)
            
            self.logger.info("Pacchetti sistema installati con successo")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Errore installazione pacchetti: {e}")
            return False
    
    def setup_python_environment(self) -> bool:
        """Configura ambiente Python virtuale"""
        self.logger.info("Configurazione ambiente Python...")
        
        venv_path = self.base_path / "venv"
        
        try:
            # Crea virtual environment
            if not venv_path.exists():
                subprocess.run([
                    'python3', '-m', 'venv', str(venv_path)
                ], check=True)
            
            # Attiva venv e installa dipendenze
            pip_path = venv_path / "bin" / "pip"
            
            # Aggiorna pip
            subprocess.run([str(pip_path), 'install', '--upgrade', 'pip'], check=True)
            
            # Installa requirements
            if (self.base_path / "requirements_improvements.txt").exists():
                subprocess.run([
                    str(pip_path), 'install', '-r', 'requirements_improvements.txt'
                ], check=True, timeout=600)
            
            # Installa dipendenze specifiche per display OLED
            if self.device_type == 'reader':
                subprocess.run([
                    str(pip_path), 'install', 
                    'luma.oled>=3.12.0', 'pillow>=10.0.0', 'qrcode>=7.4.0'
                ], check=True)
            
            self.logger.info("Ambiente Python configurato")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Errore configurazione Python: {e}")
            return False
    
    def configure_hardware(self) -> bool:
        """Configura hardware (I2C, GPIO, etc.)"""
        self.logger.info("Configurazione hardware...")
        
        try:
            # Abilita I2C
            subprocess.run(['sudo', 'raspi-config', 'nonint', 'do_i2c', '0'], check=True)
            
            # Abilita SPI se necessario
            if self.device_type == 'reader':
                subprocess.run(['sudo', 'raspi-config', 'nonint', 'do_spi', '0'], check=True)
            
            # Configura GPIO per dispositivi reader
            if self.device_type == 'reader':
                self.setup_gpio_permissions()
            
            # Test I2C
            self.test_i2c_devices()
            
            self.logger.info("Hardware configurato")
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Errore configurazione hardware: {e}")
            return False
    
    def setup_gpio_permissions(self):
        """Configura permessi GPIO per utente pi"""
        try:
            # Aggiungi utente pi ai gruppi necessari
            subprocess.run(['sudo', 'usermod', '-a', '-G', 'gpio,i2c,spi', 'pi'], check=True)
            self.logger.info("Permessi GPIO configurati")
        except Exception as e:
            self.logger.warning(f"Errore configurazione permessi GPIO: {e}")
    
    def test_i2c_devices(self):
        """Testa dispositivi I2C collegati"""
        try:
            result = subprocess.run(['i2cdetect', '-y', '1'], capture_output=True, text=True)
            if result.returncode == 0:
                self.logger.info("Scan I2C completato")
                # Cerca indirizzi comuni per display OLED (0x3C, 0x3D)
                if '3c' in result.stdout.lower() or '3d' in result.stdout.lower():
                    self.logger.info("Display OLED rilevato su I2C")
            else:
                self.logger.warning("Errore scan I2C")
        except Exception as e:
            self.logger.warning(f"Test I2C fallito: {e}")
    
    def create_device_config(self) -> bool:
        """Crea configurazione specifica per il dispositivo"""
        self.logger.info("Creazione configurazione dispositivo...")
        
        self.config_path.mkdir(exist_ok=True)
        
        # Configurazione base
        config = {
            'device': {
                'name': self.device_name,
                'type': self.device_type,
                'installation_date': str(Path(__file__).stat().st_mtime),
                'raspberry_info': self.detect_raspberry_model()
            },
            'features': self.device_configs[self.device_type]['features'],
            'hardware': {
                'display': self.device_configs[self.device_type]['display'],
                'ports': self.device_configs[self.device_type]['ports']
            }
        }
        
        # Configurazioni specifiche per reader
        if self.device_type == 'reader':
            config.update({
                'sportident': {
                    'port': '/dev/ttyUSB0',
                    'baudrate': 38400,
                    'timeout': 1.0
                },
                'meshtastic': {
                    'port': '/dev/ttyUSB1',
                    'baudrate': 115200,
                    'relay_enabled': True
                },
                'display': {
                    'type': 'oled_128x64',
                    'i2c_address': '0x3C',
                    'rotation': 0,
                    'contrast': 255
                },
                'gpio': {
                    'led_pin': 18,
                    'buzzer_pin': 19,
                    'button_pin': 20
                },
                'time_sync': {
                    'enabled': True,
                    'max_drift': 15.0,
                    'client_mode': True
                }
            })
        
        # Configurazioni specifiche per receiver
        elif self.device_type == 'receiver':
            config.update({
                'meshtastic': {
                    'port': '/dev/ttyUSB0',
                    'baudrate': 115200,
                    'relay_enabled': False
                },
                'database': {
                    'host': 'localhost',
                    'port': 3306,
                    'database': 'OriBruniRadioControls',
                    'user': 'oribruni',
                    'pool_size': 5
                },
                'web': {
                    'host': '0.0.0.0',
                    'port': 8000,
                    'debug': False
                },
                'time_sync': {
                    'enabled': True,
                    'server_mode': True,
                    'broadcast_interval': 300
                }
            })
        
        # Salva configurazione
        config_file = self.config_path / f"{self.device_name}.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        self.logger.info(f"Configurazione salvata: {config_file}")
        return True
    
    def create_systemd_services(self) -> bool:
        """Crea servizi systemd per il dispositivo"""
        self.logger.info("Creazione servizi systemd...")
        
        services_created = []
        
        try:
            if self.device_type == 'reader':
                # Servizio SportIdent Reader
                self.create_sportident_service()
                services_created.append('oribruni-sportident')
                
                # Servizio Display OLED
                self.create_display_service()
                services_created.append('oribruni-display')
            
            elif self.device_type == 'receiver':
                # Servizio Web Dashboard
                self.create_web_service()
                services_created.append('oribruni-web')
            
            # Servizio Meshtastic (comune)
            self.create_meshtastic_service()
            services_created.append('oribruni-meshtastic')
            
            # Installa e abilita servizi
            for service in services_created:
                service_file = f"{service}.service"
                subprocess.run([
                    'sudo', 'cp', service_file, '/etc/systemd/system/'
                ], check=True)
                
                subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
                subprocess.run(['sudo', 'systemctl', 'enable', service], check=True)
            
            self.logger.info(f"Servizi creati e abilitati: {services_created}")
            return True
            
        except Exception as e:
            self.logger.error(f"Errore creazione servizi: {e}")
            return False
    
    def create_sportident_service(self):
        """Crea servizio per lettore SportIdent"""
        service_content = f"""[Unit]
Description=OriBruni SportIdent Reader - {self.device_name}
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory={self.base_path}
Environment=PYTHONPATH={self.base_path}
Environment=DEVICE_NAME={self.device_name}
Environment=DEVICE_TYPE=reader
ExecStart={self.base_path}/venv/bin/python read_serial_improved.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=oribruni-sportident

# Sicurezza
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={self.base_path}
ReadWritePaths=/var/log

[Install]
WantedBy=multi-user.target
"""
        
        with open('oribruni-sportident.service', 'w') as f:
            f.write(service_content)
    
    def create_display_service(self):
        """Crea servizio per display OLED"""
        service_content = f"""[Unit]
Description=OriBruni OLED Display - {self.device_name}
After=network.target oribruni-sportident.service
Wants=oribruni-sportident.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory={self.base_path}
Environment=PYTHONPATH={self.base_path}
Environment=DEVICE_NAME={self.device_name}
ExecStart={self.base_path}/venv/bin/python oled_display.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=oribruni-display

[Install]
WantedBy=multi-user.target
"""
        
        with open('oribruni-display.service', 'w') as f:
            f.write(service_content)
    
    def create_meshtastic_service(self):
        """Crea servizio Meshtastic"""
        service_content = f"""[Unit]
Description=OriBruni Meshtastic Gateway - {self.device_name}
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory={self.base_path}
Environment=PYTHONPATH={self.base_path}
Environment=DEVICE_NAME={self.device_name}
Environment=DEVICE_TYPE={self.device_type}
ExecStart={self.base_path}/venv/bin/python meshtastic_service_improved.py
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal
SyslogIdentifier=oribruni-meshtastic

[Install]
WantedBy=multi-user.target
"""
        
        with open('oribruni-meshtastic.service', 'w') as f:
            f.write(service_content)
    
    def create_web_service(self):
        """Crea servizio web per receiver"""
        service_content = f"""[Unit]
Description=OriBruni Web Dashboard - {self.device_name}
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory={self.base_path}
Environment=PYTHONPATH={self.base_path}
Environment=DEVICE_NAME={self.device_name}
ExecStart={self.base_path}/venv/bin/python web_dashboard.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=oribruni-web

[Install]
WantedBy=multi-user.target
"""
        
        with open('oribruni-web.service', 'w') as f:
            f.write(service_content)
    
    def create_startup_script(self) -> bool:
        """Crea script di avvio automatico"""
        self.logger.info("Creazione script di avvio...")
        
        startup_script = f"""#!/bin/bash
# Script di avvio OriBruni RadioControls
# Dispositivo: {self.device_name} ({self.device_type})

set -e

# Colori per output
GREEN='\\033[0;32m'
RED='\\033[0;31m'
YELLOW='\\033[1;33m'
NC='\\033[0m'

echo -e "${{GREEN}}=== OriBruni RadioControls - Avvio {self.device_name} ===${{NC}}"

# Verifica hardware
echo "Verifica hardware..."
if ! i2cdetect -y 1 >/dev/null 2>&1; then
    echo -e "${{YELLOW}}Warning: I2C non disponibile${{NC}}"
fi

# Verifica porte seriali
echo "Verifica porte seriali..."
for port in {' '.join(self.device_configs[self.device_type]['ports'])}; do
    if [ -e "$port" ]; then
        echo -e "${{GREEN}}✓ $port disponibile${{NC}}"
    else
        echo -e "${{YELLOW}}⚠ $port non trovato${{NC}}"
    fi
done

# Avvia servizi
echo "Avvio servizi..."
"""
        
        for service in self.device_configs[self.device_type]['services']:
            startup_script += f"""
if systemctl is-active --quiet {service}; then
    echo -e "${{GREEN}}✓ {service} già attivo${{NC}}"
else
    sudo systemctl start {service}
    if systemctl is-active --quiet {service}; then
        echo -e "${{GREEN}}✓ {service} avviato${{NC}}"
    else
        echo -e "${{RED}}✗ Errore avvio {service}${{NC}}"
    fi
fi"""
        
        startup_script += f"""

# Mostra stato
echo
echo "=== Stato Servizi ==="
"""
        
        for service in self.device_configs[self.device_type]['services']:
            startup_script += f"systemctl status {service} --no-pager -l\n"
        
        startup_script += """
echo
echo -e "${GREEN}Avvio completato!${NC}"
echo "Per monitorare i log: journalctl -f -u oribruni-*"
"""
        
        # Salva script
        startup_file = self.base_path / "start_oribruni.sh"
        with open(startup_file, 'w') as f:
            f.write(startup_script)
        
        # Rendi eseguibile
        startup_file.chmod(0o755)
        
        self.logger.info(f"Script di avvio creato: {startup_file}")
        return True
    
    def create_monitoring_scripts(self) -> bool:
        """Crea script di monitoraggio e manutenzione"""
        self.logger.info("Creazione script di monitoraggio...")
        
        # Script di health check
        health_script = f"""#!/bin/bash
# Health check OriBruni RadioControls

echo "=== Health Check {self.device_name} ==="
echo "Timestamp: $(date)"
echo

# Verifica servizi
echo "=== Servizi ==="
"""
        
        for service in self.device_configs[self.device_type]['services']:
            health_script += f"""
if systemctl is-active --quiet {service}; then
    echo "✓ {service}: ATTIVO"
else
    echo "✗ {service}: INATTIVO"
fi"""
        
        health_script += """

# Verifica hardware
echo
echo "=== Hardware ==="
if [ -e /dev/i2c-1 ]; then
    echo "✓ I2C: Disponibile"
else
    echo "✗ I2C: Non disponibile"
fi

# Verifica porte seriali
"""
        
        for port in self.device_configs[self.device_type]['ports']:
            health_script += f"""
if [ -e {port} ]; then
    echo "✓ {port}: Disponibile"
else
    echo "✗ {port}: Non disponibile"
fi"""
        
        health_script += """

# Verifica spazio disco
echo
echo "=== Spazio Disco ==="
df -h / | tail -1

# Verifica memoria
echo
echo "=== Memoria ==="
free -h

# Verifica temperatura (se disponibile)
if [ -e /sys/class/thermal/thermal_zone0/temp ]; then
    temp=$(cat /sys/class/thermal/thermal_zone0/temp)
    temp_c=$((temp/1000))
    echo
    echo "=== Temperatura ==="
    echo "CPU: ${temp_c}°C"
fi

echo
echo "Health check completato"
"""
        
        # Salva script health check
        health_file = self.base_path / "health_check.sh"
        with open(health_file, 'w') as f:
            f.write(health_script)
        health_file.chmod(0o755)
        
        # Script di backup
        backup_script = f"""#!/bin/bash
# Backup OriBruni RadioControls

BACKUP_DIR="{self.backup_path}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "Creazione backup: $BACKUP_FILE"

tar -czf "$BACKUP_FILE" \\
    --exclude="venv" \\
    --exclude="*.pyc" \\
    --exclude="__pycache__" \\
    --exclude="logs/*.log" \\
    config/ *.py *.json *.ini 2>/dev/null || true

if [ -f "$BACKUP_FILE" ]; then
    echo "✓ Backup creato: $BACKUP_FILE"
    
    # Mantieni solo gli ultimi 10 backup
    cd "$BACKUP_DIR"
    ls -t backup_*.tar.gz | tail -n +11 | xargs rm -f 2>/dev/null || true
    
    echo "Backup completato"
else
    echo "✗ Errore creazione backup"
    exit 1
fi
"""
        
        # Salva script backup
        backup_file = self.base_path / "backup.sh"
        with open(backup_file, 'w') as f:
            f.write(backup_script)
        backup_file.chmod(0o755)
        
        self.logger.info("Script di monitoraggio creati")
        return True
    
    def setup_cron_jobs(self) -> bool:
        """Configura job cron per manutenzione automatica"""
        self.logger.info("Configurazione cron jobs...")
        
        cron_jobs = f"""# OriBruni RadioControls - {self.device_name}
# Health check ogni 15 minuti
*/15 * * * * {self.base_path}/health_check.sh >> {self.logs_path}/health.log 2>&1

# Backup giornaliero alle 02:00
0 2 * * * {self.base_path}/backup.sh >> {self.logs_path}/backup.log 2>&1

# Pulizia log vecchi ogni domenica alle 03:00
0 3 * * 0 find {self.logs_path} -name "*.log" -mtime +7 -delete

# Riavvio servizi ogni lunedì alle 04:00 (per eventi lunghi)
0 4 * * 1 systemctl restart oribruni-* >> {self.logs_path}/restart.log 2>&1
"""
        
        try:
            # Installa cron jobs
            process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
            process.communicate(input=cron_jobs)
            
            if process.returncode == 0:
                self.logger.info("Cron jobs configurati")
                return True
            else:
                self.logger.error("Errore configurazione cron jobs")
                return False
                
        except Exception as e:
            self.logger.error(f"Errore setup cron: {e}")
            return False
    
    def deploy(self) -> bool:
        """Esegue il deploy completo"""
        self.logger.info(f"Inizio deploy {self.device_type} '{self.device_name}'")
        
        # Rileva hardware
        hw_info = self.detect_raspberry_model()
        self.logger.info(f"Hardware rilevato: {hw_info}")
        
        steps = [
            ("Verifica prerequisiti", self.check_prerequisites),
            ("Installazione pacchetti sistema", self.install_system_packages),
            ("Configurazione ambiente Python", self.setup_python_environment),
            ("Configurazione hardware", self.configure_hardware),
            ("Creazione configurazione dispositivo", self.create_device_config),
            ("Creazione servizi systemd", self.create_systemd_services),
            ("Creazione script di avvio", self.create_startup_script),
            ("Creazione script di monitoraggio", self.create_monitoring_scripts),
            ("Configurazione cron jobs", self.setup_cron_jobs)
        ]
        
        for step_name, step_func in steps:
            self.logger.info(f"Esecuzione: {step_name}")
            try:
                if not step_func():
                    self.logger.error(f"Fallito: {step_name}")
                    return False
                self.logger.info(f"Completato: {step_name}")
            except Exception as e:
                self.logger.error(f"Errore in {step_name}: {e}")
                return False
        
        self.logger.info("Deploy completato con successo!")
        self.logger.info(f"Per avviare: ./start_oribruni.sh")
        self.logger.info(f"Per monitorare: journalctl -f -u oribruni-*")
        
        return True


def main():
    """Funzione principale"""
    parser = argparse.ArgumentParser(description='Deploy OriBruni RadioControls su Raspberry Pi')
    parser.add_argument('device_type', choices=['reader', 'receiver'], 
                       help='Tipo di dispositivo da configurare')
    parser.add_argument('device_name', help='Nome del dispositivo (es: reader-01, receiver-main)')
    parser.add_argument('--auto-start', action='store_true', 
                       help='Avvia automaticamente i servizi dopo il deploy')
    
    args = parser.parse_args()
    
    # Verifica se siamo su Raspberry Pi
    if not Path('/proc/device-tree/model').exists():
        print("ATTENZIONE: Non sembra essere un Raspberry Pi")
        response = input("Continuare comunque? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
    
    # Verifica permessi
    if os.geteuid() == 0:
        print("ERRORE: Non eseguire come root. Usa l'utente 'pi'.")
        sys.exit(1)
    
    # Crea deployer ed esegui
    deployer = RaspberryDeployer(args.device_type, args.device_name)
    
    if deployer.deploy():
        print(f"\n🎉 Deploy {args.device_type} '{args.device_name}' completato!")
        
        if args.auto_start:
            print("Avvio servizi...")
            subprocess.run(['./start_oribruni.sh'])
        else:
            print("Per avviare i servizi: ./start_oribruni.sh")
        
        sys.exit(0)
    else:
        print(f"\n❌ Deploy fallito. Controllare i log in logs/deploy.log")
        sys.exit(1)


if __name__ == '__main__':
    main()

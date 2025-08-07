#!/bin/bash
# Script di installazione miglioramenti OriBruniRadioControls
# Eseguire con: chmod +x install_improvements.sh && ./install_improvements.sh

set -e  # Exit on error

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funzioni utility
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verifica se siamo su Raspberry Pi
is_raspberry_pi() {
    if [[ $(uname -m) == "armv7l" ]] || [[ $(uname -m) == "aarch64" ]]; then
        return 0
    else
        return 1
    fi
}

# Verifica prerequisiti
check_prerequisites() {
    log_info "Verifica prerequisiti..."
    
    # Verifica Python 3.8+
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 non trovato. Installare Python 3.8 o superiore."
        exit 1
    fi
    
    python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [[ $(echo "$python_version < 3.8" | bc -l) -eq 1 ]]; then
        log_error "Python $python_version trovato. Richiesto Python 3.8 o superiore."
        exit 1
    fi
    
    log_success "Python $python_version OK"
    
    # Verifica pip
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 non trovato. Installare pip3."
        exit 1
    fi
    
    # Verifica MySQL
    if ! command -v mysql &> /dev/null; then
        log_warning "MySQL client non trovato. Potrebbe essere necessario installarlo."
    fi
    
    # Verifica Git
    if ! command -v git &> /dev/null; then
        log_warning "Git non trovato. Potrebbe essere necessario per alcuni aggiornamenti."
    fi
}

# Backup configurazione esistente
backup_config() {
    log_info "Backup configurazione esistente..."
    
    if [[ -f "config.ini" ]]; then
        backup_file="config.ini.backup.$(date +%Y%m%d_%H%M%S)"
        cp config.ini "$backup_file"
        log_success "Backup creato: $backup_file"
    fi
    
    # Backup altri file importanti
    for file in "read_serial.py" "meshtastic_service.py"; do
        if [[ -f "$file" ]]; then
            backup_file="${file}.backup.$(date +%Y%m%d_%H%M%S)"
            cp "$file" "$backup_file"
            log_success "Backup creato: $backup_file"
        fi
    done
}

# Installa dipendenze Python
install_python_dependencies() {
    log_info "Installazione dipendenze Python..."
    
    # Aggiorna pip
    python3 -m pip install --upgrade pip
    
    # Installa wheel per compilazioni più veloci
    python3 -m pip install wheel
    
    # Installa dipendenze base
    if [[ -f "requirements_improvements.txt" ]]; then
        log_info "Installazione da requirements_improvements.txt..."
        python3 -m pip install -r requirements_improvements.txt
    else
        log_warning "requirements_improvements.txt non trovato, installazione dipendenze base..."
        python3 -m pip install cryptography python-dotenv mysql-connector-python psutil fastapi uvicorn
    fi
    
    log_success "Dipendenze Python installate"
}

# Installa dipendenze sistema (Ubuntu/Debian)
install_system_dependencies() {
    log_info "Installazione dipendenze sistema..."
    
    if command -v apt-get &> /dev/null; then
        # Aggiorna package list
        sudo apt-get update
        
        # Installa dipendenze base
        sudo apt-get install -y \
            build-essential \
            python3-dev \
            libssl-dev \
            libffi-dev \
            libmysqlclient-dev \
            pkg-config \
            redis-server \
            nginx \
            supervisor
        
        # Dipendenze specifiche per Raspberry Pi
        if is_raspberry_pi; then
            log_info "Installazione dipendenze Raspberry Pi..."
            sudo apt-get install -y \
                i2c-tools \
                python3-smbus \
                wiringpi \
                gpio
            
            # Abilita I2C
            sudo raspi-config nonint do_i2c 0
        fi
        
        log_success "Dipendenze sistema installate"
    else
        log_warning "apt-get non trovato. Installare manualmente le dipendenze sistema."
    fi
}

# Configura Redis
setup_redis() {
    log_info "Configurazione Redis..."
    
    if command -v redis-server &> /dev/null; then
        # Configura Redis per uso locale
        sudo systemctl enable redis-server
        sudo systemctl start redis-server
        
        # Test connessione Redis
        if redis-cli ping | grep -q "PONG"; then
            log_success "Redis configurato e funzionante"
        else
            log_warning "Redis installato ma non risponde"
        fi
    else
        log_warning "Redis non installato"
    fi
}

# Configura database
setup_database() {
    log_info "Configurazione database..."
    
    # Crea indici ottimizzati se il database esiste
    if command -v mysql &> /dev/null; then
        log_info "Creazione indici database ottimizzati..."
        
        # Script SQL per indici
        cat > create_indexes.sql << 'EOF'
-- Indici ottimizzati per OriBruniRadioControls
USE OriBruniRadioControls;

-- Indici per tabella radiocontrol
CREATE INDEX IF NOT EXISTS idx_radiocontrol_timestamp ON radiocontrol(timestamp);
CREATE INDEX IF NOT EXISTS idx_radiocontrol_punch_time ON radiocontrol(punch_time);
CREATE INDEX IF NOT EXISTS idx_radiocontrol_sent_internet ON radiocontrol(sent_internet);
CREATE INDEX IF NOT EXISTS idx_radiocontrol_control_card ON radiocontrol(control, card_number);

-- Indici per tabella punches
CREATE INDEX IF NOT EXISTS idx_punches_punch_time ON punches(punch_time);
CREATE INDEX IF NOT EXISTS idx_punches_timestamp ON punches(timestamp);
CREATE INDEX IF NOT EXISTS idx_punches_control_card ON punches(control, card_number);

-- Indici per tabella meshtastic_log
CREATE INDEX IF NOT EXISTS idx_meshtastic_log_event_time ON meshtastic_log(event_time);
CREATE INDEX IF NOT EXISTS idx_meshtastic_log_direction_type ON meshtastic_log(direction, msg_type);
CREATE INDEX IF NOT EXISTS idx_meshtastic_log_node_name ON meshtastic_log(node_name);

-- Indici per tabella messaggi
CREATE INDEX IF NOT EXISTS idx_messaggi_data_ora ON messaggi(data_ora);
CREATE INDEX IF NOT EXISTS idx_messaggi_id_nodo ON messaggi(id_nodo);
CREATE INDEX IF NOT EXISTS idx_messaggi_tipo ON messaggi(tipo_messaggio);

-- Indici per tabella nodes
CREATE INDEX IF NOT EXISTS idx_nodes_last_signal ON nodes(last_signal);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);

-- Indici per tabella log
CREATE INDEX IF NOT EXISTS idx_log_timestamp ON log(timestamp);
CREATE INDEX IF NOT EXISTS idx_log_nome ON log(nome);

SHOW INDEX FROM radiocontrol;
SHOW INDEX FROM punches;
SHOW INDEX FROM meshtastic_log;
EOF
        
        log_info "Eseguire manualmente: mysql -u root -p < create_indexes.sql"
        log_success "Script SQL creato: create_indexes.sql"
    else
        log_warning "MySQL client non trovato, saltata configurazione database"
    fi
}

# Migra configurazione esistente
migrate_config() {
    log_info "Migrazione configurazione..."
    
    if [[ -f "config.ini" ]]; then
        # Usa il config manager per migrare
        if [[ -f "config_manager.py" ]]; then
            python3 -c "
from config_manager import migrate_existing_config
migrate_existing_config('config.ini', backup=False)
print('Configurazione migrata con successo')
"
            log_success "Configurazione migrata al nuovo formato sicuro"
        else
            log_warning "config_manager.py non trovato, migrazione saltata"
        fi
    else
        log_info "Nessuna configurazione esistente da migrare"
    fi
}

# Configura servizi systemd
setup_services() {
    log_info "Configurazione servizi systemd..."
    
    # Crea servizio per read_serial migliorato
    if [[ -f "read_serial.py" ]]; then
        cat > oribruni-sportident.service << EOF
[Unit]
Description=OriBruni SportIdent Reader Service
After=network.target mysql.service redis.service
Wants=mysql.service redis.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=$(pwd)
Environment=PYTHONPATH=$(pwd)
Environment=ORIBRUNI_ENV=production
ExecStart=/usr/bin/python3 read_serial.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=oribruni-sportident

# Sicurezza
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$(pwd)
ReadWritePaths=/var/log

[Install]
WantedBy=multi-user.target
EOF
        
        log_success "Servizio oribruni-sportident.service creato"
    fi
    
    # Crea servizio per meshtastic
    if [[ -f "Meshtastic/Raspberry_RADIOCONTROL/meshtastic_service.py" ]]; then
        cat > oribruni-meshtastic.service << EOF
[Unit]
Description=OriBruni Meshtastic Service
After=network.target mysql.service redis.service
Wants=mysql.service redis.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=$(pwd)/Meshtastic/Raspberry_RADIOCONTROL
Environment=PYTHONPATH=$(pwd)
Environment=ORIBRUNI_ENV=production
ExecStart=/usr/bin/python3 meshtastic_service.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=oribruni-meshtastic

# Sicurezza
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$(pwd)
ReadWritePaths=/var/log

[Install]
WantedBy=multi-user.target
EOF
        
        log_success "Servizio oribruni-meshtastic.service creato"
    fi
    
    log_info "Per installare i servizi eseguire:"
    log_info "  sudo cp *.service /etc/systemd/system/"
    log_info "  sudo systemctl daemon-reload"
    log_info "  sudo systemctl enable oribruni-sportident oribruni-meshtastic"
}

# Configura monitoring
setup_monitoring() {
    log_info "Configurazione monitoring..."
    
    # Crea script di health check
    cat > health_check.py << 'EOF'
#!/usr/bin/env python3
"""Health check script per OriBruniRadioControls"""

import sys
import json
from config_manager import ConfigManager
from database_manager import DatabaseManager

def main():
    try:
        # Test configurazione
        config = ConfigManager()
        print("✓ Configurazione OK")
        
        # Test database
        db_manager = DatabaseManager(config)
        health = db_manager.health_check()
        
        if health['database'] == 'healthy':
            print("✓ Database OK")
        else:
            print(f"✗ Database: {health.get('error', 'Unknown error')}")
            return 1
        
        # Test Redis se disponibile
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
            print("✓ Redis OK")
        except:
            print("⚠ Redis non disponibile")
        
        print("Health check completato con successo")
        return 0
        
    except Exception as e:
        print(f"✗ Health check fallito: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
EOF
    
    chmod +x health_check.py
    log_success "Script health check creato: health_check.py"
    
    # Crea cron job per monitoring
    cat > monitoring_cron << 'EOF'
# OriBruni Monitoring Cron Jobs
# Aggiungi con: crontab -e

# Health check ogni 5 minuti
*/5 * * * * cd /home/pi/OriBruniRadioControls && python3 health_check.py >> /var/log/oribruni-health.log 2>&1

# Backup database giornaliero
0 2 * * * mysqldump -u root -p OriBruniRadioControls > /home/pi/backup/oribruni_$(date +\%Y\%m\%d).sql

# Pulizia log vecchi (>30 giorni)
0 3 * * 0 find /var/log -name "oribruni-*.log" -mtime +30 -delete
EOF
    
    log_success "Template cron job creato: monitoring_cron"
}

# Crea script di test
create_test_script() {
    log_info "Creazione script di test..."
    
    cat > test_improvements.py << 'EOF'
#!/usr/bin/env python3
"""Test script per verificare i miglioramenti"""

import sys
import logging
from config_manager import ConfigManager
from database_manager import DatabaseManager
from thread_safe_buffer import ThreadSafeBuffer, MessageQueue

logging.basicConfig(level=logging.INFO)

def test_config_manager():
    """Test ConfigManager"""
    print("Testing ConfigManager...")
    try:
        config = ConfigManager()
        
        # Test crittografia
        test_password = "test123"
        encrypted = config.encrypt_password(test_password)
        decrypted = config.decrypt_password(encrypted)
        
        assert test_password == decrypted, "Crittografia fallita"
        print("✓ ConfigManager OK")
        return True
    except Exception as e:
        print(f"✗ ConfigManager: {e}")
        return False

def test_database_manager():
    """Test DatabaseManager"""
    print("Testing DatabaseManager...")
    try:
        config = ConfigManager()
        db_manager = DatabaseManager(config)
        
        health = db_manager.health_check()
        assert health['database'] == 'healthy', f"Database unhealthy: {health}"
        
        print("✓ DatabaseManager OK")
        return True
    except Exception as e:
        print(f"✗ DatabaseManager: {e}")
        return False

def test_thread_safe_buffer():
    """Test ThreadSafeBuffer"""
    print("Testing ThreadSafeBuffer...")
    try:
        buffer = ThreadSafeBuffer()
        
        # Test basic operations
        test_data = b'\xFF\x02\xD3\x08\x31\x32\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x03'
        buffer.extend(test_data)
        
        frame_info = buffer.extract_frame()
        assert frame_info is not None, "Frame extraction failed"
        
        print("✓ ThreadSafeBuffer OK")
        return True
    except Exception as e:
        print(f"✗ ThreadSafeBuffer: {e}")
        return False

def test_message_queue():
    """Test MessageQueue"""
    print("Testing MessageQueue...")
    try:
        queue = MessageQueue()
        
        # Test priority queue
        queue.put("low", priority=1)
        queue.put("high", priority=5)
        queue.put("medium", priority=3)
        
        # Should get high priority first
        message, priority, timestamp = queue.get_nowait()
        assert priority == 5, f"Expected priority 5, got {priority}"
        
        print("✓ MessageQueue OK")
        return True
    except Exception as e:
        print(f"✗ MessageQueue: {e}")
        return False

def main():
    """Run all tests"""
    print("=== Test Miglioramenti OriBruniRadioControls ===\n")
    
    tests = [
        test_config_manager,
        test_database_manager,
        test_thread_safe_buffer,
        test_message_queue
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1
        print()
    
    print(f"=== Risultati: {passed} passed, {failed} failed ===")
    
    if failed == 0:
        print("🎉 Tutti i test sono passati!")
        return 0
    else:
        print("❌ Alcuni test sono falliti")
        return 1

if __name__ == '__main__':
    sys.exit(main())
EOF
    
    chmod +x test_improvements.py
    log_success "Script di test creato: test_improvements.py"
}

# Funzione principale
main() {
    echo "=================================================="
    echo "  OriBruniRadioControls - Installazione Miglioramenti"
    echo "=================================================="
    echo
    
    # Verifica se siamo nella directory corretta
    if [[ ! -f "read_serial.py" ]] && [[ ! -f "config.ini" ]]; then
        log_error "Eseguire lo script dalla directory del progetto OriBruniRadioControls"
        exit 1
    fi
    
    # Verifica prerequisiti
    check_prerequisites
    
    # Backup configurazione
    backup_config
    
    # Installazione dipendenze
    install_system_dependencies
    install_python_dependencies
    
    # Configurazione servizi
    setup_redis
    setup_database
    
    # Migrazione configurazione
    migrate_config
    
    # Setup servizi e monitoring
    setup_services
    setup_monitoring
    
    # Crea script di test
    create_test_script
    
    echo
    log_success "Installazione miglioramenti completata!"
    echo
    echo "Prossimi passi:"
    echo "1. Eseguire test: python3 test_improvements.py"
    echo "2. Configurare database: mysql -u root -p < create_indexes.sql"
    echo "3. Installare servizi systemd (vedi output sopra)"
    echo "4. Configurare cron jobs: crontab -e (vedi monitoring_cron)"
    echo "5. Riavviare i servizi: sudo systemctl restart oribruni-*"
    echo
    log_info "Per supporto, consultare ANALISI_COMPLETA_E_ROADMAP.md"
}

# Esegui solo se chiamato direttamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

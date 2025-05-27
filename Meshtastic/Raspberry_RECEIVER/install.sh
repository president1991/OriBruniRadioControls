#!/bin/bash

# ============================================================================
# Script di Installazione OriBruni Raspberry RECEIVER
# ============================================================================
# Questo script automatizza l'installazione completa del sistema receiver
# per Raspberry Pi con Raspbian/Raspberry Pi OS
# 
# Utilizzo: chmod +x install.sh && sudo ./install.sh
# ============================================================================

set -e  # Esce in caso di errore

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funzioni di utilità
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

# Verifica se lo script è eseguito come root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Questo script deve essere eseguito come root (sudo)"
        exit 1
    fi
}

# Aggiorna il sistema
update_system() {
    log_info "Aggiornamento del sistema..."
    apt update && apt upgrade -y
    log_success "Sistema aggiornato"
}

# Installa dipendenze di sistema
install_system_dependencies() {
    log_info "Installazione dipendenze di sistema..."
    
    apt install -y \
        python3 \
        python3-pip \
        python3-dev \
        python3-venv \
        build-essential \
        libmariadb-dev \
        pkg-config \
        i2c-tools \
        python3-smbus \
        git \
        curl \
        wget \
        mariadb-server \
        mariadb-client \
        nginx \
        supervisor \
        ufw \
        php \
        php-fpm \
        php-mysql \
        php-mbstring \
        php-zip \
        php-gd \
        php-json \
        php-curl \
        phpmyadmin
    
    log_success "Dipendenze di sistema installate"
}

# Abilita I2C
enable_i2c() {
    log_info "Abilitazione interfaccia I2C..."
    
    # Abilita I2C nel config.txt se non già presente
    if ! grep -q "dtparam=i2c_arm=on" /boot/config.txt; then
        echo "dtparam=i2c_arm=on" >> /boot/config.txt
        log_info "I2C abilitato in /boot/config.txt"
    fi
    
    # Carica il modulo I2C
    modprobe i2c-dev
    
    # Aggiungi l'utente pi al gruppo i2c
    usermod -a -G i2c pi
    
    log_success "I2C configurato"
}

# Configura MariaDB
setup_database() {
    log_info "Configurazione database MariaDB..."
    
    # Avvia MariaDB
    systemctl start mariadb
    systemctl enable mariadb
    
    # Configurazione sicura di MariaDB (automatica)
    mysql -e "UPDATE mysql.user SET Password=PASSWORD('PuhA7gWCrW') WHERE User='root'"
    mysql -e "DELETE FROM mysql.user WHERE User=''"
    mysql -e "DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1')"
    mysql -e "DROP DATABASE IF EXISTS test"
    mysql -e "DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%'"
    mysql -e "FLUSH PRIVILEGES"
    
    # Crea database e utente per l'applicazione
    mysql -u root -pPuhA7gWCrW -e "CREATE DATABASE IF NOT EXISTS OriBruniRadioControls"
    mysql -u root -pPuhA7gWCrW -e "CREATE USER IF NOT EXISTS 'meshdash'@'localhost' IDENTIFIED BY 'MeshDash2025!'"
    mysql -u root -pPuhA7gWCrW -e "GRANT ALL PRIVILEGES ON OriBruniRadioControls.* TO 'meshdash'@'localhost'"
    mysql -u root -pPuhA7gWCrW -e "FLUSH PRIVILEGES"
    
    log_success "Database configurato"
}

# Crea tabelle database
create_database_tables() {
    log_info "Creazione tabelle database..."
    
    mysql -u meshdash -pMeshDash2025! OriBruniRadioControls << EOF
CREATE TABLE IF NOT EXISTS messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  timestamp DATETIME NOT NULL,
  node_eui VARCHAR(32),
  field1 VARCHAR(255),
  field2 VARCHAR(255),
  field3 VARCHAR(255),
  raw TEXT,
  INDEX idx_timestamp (timestamp),
  INDEX idx_node_eui (node_eui)
);

CREATE TABLE IF NOT EXISTS punches (
  id INT AUTO_INCREMENT PRIMARY KEY,
  timestamp DATETIME NOT NULL,
  name VARCHAR(255),
  pkey VARCHAR(255),
  record_id VARCHAR(255),
  control VARCHAR(255),
  card_number VARCHAR(255),
  punch_time VARCHAR(255),
  raw TEXT,
  INDEX idx_timestamp (timestamp),
  INDEX idx_record_id (record_id),
  INDEX idx_control (control)
);
EOF
    
    log_success "Tabelle database create"
}

# Configura ambiente Python
setup_python_environment() {
    log_info "Configurazione ambiente Python..."
    
    # Crea directory applicazione
    mkdir -p /opt/oribruni-receiver
    cd /opt/oribruni-receiver
    
    # Copia file del progetto
    cp -r /home/pi/OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER/* .
    
    # Crea ambiente virtuale
    python3 -m venv venv
    source venv/bin/activate
    
    # Aggiorna pip
    pip install --upgrade pip
    
    # Installa requirements
    pip install -r requirements.txt
    
    # Imposta permessi
    chown -R pi:pi /opt/oribruni-receiver
    
    log_success "Ambiente Python configurato"
}

# Configura servizi systemd
setup_systemd_services() {
    log_info "Configurazione servizi systemd..."
    
    # Servizio principale receiver
    cat > /etc/systemd/system/oribruni-receiver.service << EOF
[Unit]
Description=OriBruni Receiver Service
After=network.target mariadb.service
Wants=mariadb.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/oribruni-receiver
Environment=PATH=/opt/oribruni-receiver/venv/bin
ExecStart=/opt/oribruni-receiver/venv/bin/python server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Servizio LCD display
    cat > /etc/systemd/system/oribruni-lcd.service << EOF
[Unit]
Description=OriBruni LCD Display Service
After=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/oribruni-receiver/lcd_display
Environment=PATH=/opt/oribruni-receiver/venv/bin
ExecStart=/opt/oribruni-receiver/venv/bin/python lcd_display.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Ricarica systemd e abilita servizi
    systemctl daemon-reload
    systemctl enable oribruni-receiver.service
    systemctl enable oribruni-lcd.service
    
    log_success "Servizi systemd configurati"
}

# Configura Nginx
setup_nginx() {
    log_info "Configurazione Nginx..."
    
    cat > /etc/nginx/sites-available/oribruni-receiver << EOF
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    
    # Abilita il sito
    ln -sf /etc/nginx/sites-available/oribruni-receiver /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    # Testa configurazione e riavvia
    nginx -t
    systemctl restart nginx
    systemctl enable nginx
    
    log_success "Nginx configurato"
}

# Configura firewall
setup_firewall() {
    log_info "Configurazione firewall..."
    
    ufw --force enable
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    log_success "Firewall configurato"
}

# Crea script di backup
create_backup_script() {
    log_info "Creazione script di backup..."
    
    cat > /opt/oribruni-receiver/backup.sh << 'EOF'
#!/bin/bash
# Script di backup automatico

BACKUP_DIR="/opt/oribruni-receiver/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.sql"

mkdir -p $BACKUP_DIR

# Backup database
mysqldump -u meshdash -pMeshDash2025! OriBruniRadioControls > $BACKUP_FILE

# Comprimi backup
gzip $BACKUP_FILE

# Rimuovi backup più vecchi di 30 giorni
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

echo "Backup completato: $BACKUP_FILE.gz"
EOF
    
    chmod +x /opt/oribruni-receiver/backup.sh
    
    # Aggiungi cron job per backup giornaliero
    (crontab -u pi -l 2>/dev/null; echo "0 2 * * * /opt/oribruni-receiver/backup.sh") | crontab -u pi -
    
    log_success "Script di backup configurato"
}

# Funzione principale
main() {
    log_info "Avvio installazione OriBruni Raspberry RECEIVER..."
    
    check_root
    update_system
    install_system_dependencies
    enable_i2c
    setup_database
    create_database_tables
    setup_python_environment
    setup_systemd_services
    setup_nginx
    setup_firewall
    create_backup_script
    
    log_success "Installazione completata!"
    log_info "Riavvia il sistema per applicare tutte le modifiche: sudo reboot"
    log_info "Dopo il riavvio, i servizi saranno disponibili su:"
    log_info "  - Web Interface: http://$(hostname -I | awk '{print $1}')"
    log_info "  - Database: MariaDB su localhost:3306"
    log_info "  - Logs: journalctl -u oribruni-receiver.service -f"
    log_warning "Password database root: OriBruni2025!"
    log_warning "Password database meshdash: MeshDash2025!"
}

# Esegui installazione
main "$@"

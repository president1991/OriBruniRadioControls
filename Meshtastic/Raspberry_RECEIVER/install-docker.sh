#!/bin/bash

# ============================================================================
# Script di Installazione Docker per OriBruni Raspberry RECEIVER
# ============================================================================
# Installazione completa automatica su Raspberry Pi
# Utilizzo: chmod +x install-docker.sh && ./install-docker.sh
# ============================================================================

set -e

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Banner
echo -e "${GREEN}"
echo "============================================================================"
echo "  OriBruni Raspberry RECEIVER - Installazione Docker"
echo "============================================================================"
echo -e "${NC}"

# Verifica sistema
log_info "Verifica sistema operativo..."
if ! grep -q "Raspberry Pi" /proc/cpuinfo; then
    log_warning "Sistema non riconosciuto come Raspberry Pi"
    read -p "Continuare comunque? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Aggiorna sistema
log_info "Aggiornamento sistema..."
sudo apt update && sudo apt upgrade -y

# Installa Docker
log_info "Installazione Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    log_success "Docker installato"
else
    log_info "Docker già installato"
fi

# Aggiungi utente al gruppo docker
log_info "Configurazione permessi Docker..."
sudo usermod -aG docker $USER

# Installa Docker Compose
log_info "Installazione Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo apt install -y docker-compose-plugin
    log_success "Docker Compose installato"
else
    log_info "Docker Compose già installato"
fi

# Abilita I2C per LCD
log_info "Configurazione I2C per display LCD..."
if ! grep -q "dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
    log_info "I2C abilitato in /boot/config.txt"
fi

# Installa i2c-tools
sudo apt install -y i2c-tools

# Installa git se non presente
log_info "Verifica installazione Git..."
if ! command -v git &> /dev/null; then
    sudo apt install -y git
    log_success "Git installato"
fi

# Clona repository se non siamo già nella directory del progetto
if [ ! -f "docker-compose.yml" ]; then
    log_info "Clone repository OriBruni..."
    cd "$HOME"
    if [ -d "OriBruniRadioControls" ]; then
        log_info "Repository già presente, aggiornamento..."
        cd OriBruniRadioControls
        git pull
    else
        git clone https://github.com/president1991/OriBruniRadioControls.git
        cd OriBruniRadioControls
    fi
    cd Meshtastic/Raspberry_RECEIVER
else
    log_info "Già nella directory del progetto"
fi

# Crea directory di lavoro
PROJECT_DIR="$HOME/oribruni-receiver"
log_info "Creazione directory di lavoro: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"

# Copia file progetto nella directory di lavoro
log_info "Copia file progetto..."
cp -r * "$PROJECT_DIR/"
cd "$PROJECT_DIR"

# Crea struttura directory
log_info "Creazione struttura directory..."
mkdir -p {data/mysql,logs/nginx,backups,nginx/ssl}

# Imposta permessi
log_info "Configurazione permessi..."
chmod +x scripts/backup.sh 2>/dev/null || true
chmod 755 data logs backups

# Crea file .env con configurazioni
log_info "Creazione file di configurazione..."
cat > .env << EOF
# Configurazione OriBruni Receiver
MYSQL_ROOT_PASSWORD=PuhA7gWCrW
MYSQL_PASSWORD=MeshDash2025!
FLASK_ENV=production
LOG_LEVEL=INFO
RETENTION_DAYS=30
VERIFY_BACKUP=false
EOF

# Test Docker
log_info "Test installazione Docker..."
if docker --version && docker compose version; then
    log_success "Docker installato correttamente"
else
    log_error "Errore nell'installazione Docker"
    exit 1
fi

# Informazioni finali
echo
log_success "Installazione completata!"
echo
log_info "Prossimi passi:"
echo "1. Riavvia il sistema: sudo reboot"
echo "2. Dopo il riavvio, vai nella directory: cd $PROJECT_DIR"
echo "3. Avvia i servizi: make up"
echo "4. Verifica stato: make status"
echo "5. Accedi all'interfaccia web: http://$(hostname -I | awk '{print $1}')"
echo
log_info "Comandi utili:"
echo "  make help       - Mostra tutti i comandi disponibili"
echo "  make up         - Avvia tutti i servizi"
echo "  make down       - Ferma tutti i servizi"
echo "  make logs       - Mostra logs in tempo reale"
echo "  make status     - Stato servizi"
echo "  make db-backup  - Backup database"
echo
log_warning "IMPORTANTE: Riavvia il sistema per completare l'installazione!"
echo "sudo reboot"

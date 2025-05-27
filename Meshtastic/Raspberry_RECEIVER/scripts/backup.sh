#!/bin/bash

# ============================================================================
# Script di Backup Database per Docker
# ============================================================================
# Esegue backup del database MySQL in ambiente Docker
# ============================================================================

set -e

# Configurazione
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/oribruni_backup_$DATE.sql"
MYSQL_HOST=${MYSQL_HOST:-mysql}
MYSQL_USER=${MYSQL_USER:-root}
MYSQL_PASSWORD=${MYSQL_PASSWORD:-PuhA7gWCrW}
MYSQL_DATABASE=${MYSQL_DATABASE:-OriBruniRadioControls}
RETENTION_DAYS=${RETENTION_DAYS:-30}

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

# Crea directory backup se non esiste
mkdir -p "$BACKUP_DIR"

log_info "Avvio backup database OriBruni..."
log_info "Host: $MYSQL_HOST"
log_info "Database: $MYSQL_DATABASE"
log_info "File backup: $BACKUP_FILE"

# Attendi che MySQL sia disponibile
log_info "Verifica connessione database..."
for i in {1..30}; do
    if mysqladmin ping -h"$MYSQL_HOST" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" --silent; then
        log_success "Database raggiungibile"
        break
    fi
    if [ $i -eq 30 ]; then
        log_error "Impossibile connettersi al database dopo 30 tentativi"
        exit 1
    fi
    log_info "Tentativo $i/30 - Attendo database..."
    sleep 2
done

# Esegui backup
log_info "Esecuzione backup..."
mysqldump \
    -h"$MYSQL_HOST" \
    -u"$MYSQL_USER" \
    -p"$MYSQL_PASSWORD" \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    --add-drop-database \
    --add-drop-table \
    --create-options \
    --disable-keys \
    --extended-insert \
    --quick \
    --lock-tables=false \
    "$MYSQL_DATABASE" > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    log_success "Backup database completato"
else
    log_error "Errore durante il backup"
    exit 1
fi

# Comprimi backup
log_info "Compressione backup..."
gzip "$BACKUP_FILE"
COMPRESSED_FILE="$BACKUP_FILE.gz"

if [ -f "$COMPRESSED_FILE" ]; then
    BACKUP_SIZE=$(du -h "$COMPRESSED_FILE" | cut -f1)
    log_success "Backup compresso: $COMPRESSED_FILE ($BACKUP_SIZE)"
else
    log_error "Errore durante la compressione"
    exit 1
fi

# Pulizia backup vecchi
log_info "Pulizia backup più vecchi di $RETENTION_DAYS giorni..."
DELETED_COUNT=$(find "$BACKUP_DIR" -name "oribruni_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
if [ $DELETED_COUNT -gt 0 ]; then
    log_info "Rimossi $DELETED_COUNT backup vecchi"
else
    log_info "Nessun backup vecchio da rimuovere"
fi

# Statistiche backup
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -name "oribruni_backup_*.sql.gz" | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

log_success "Backup completato con successo!"
log_info "Statistiche:"
log_info "  - File backup: $COMPRESSED_FILE"
log_info "  - Dimensione: $BACKUP_SIZE"
log_info "  - Totale backup: $TOTAL_BACKUPS"
log_info "  - Spazio utilizzato: $TOTAL_SIZE"

# Registra evento nel database
mysql -h"$MYSQL_HOST" -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" << EOF
INSERT INTO system_events (event_type, source, message, details) VALUES
('INFO', 'BACKUP', 'Backup database completato', 
JSON_OBJECT(
    'backup_file', '$COMPRESSED_FILE',
    'backup_size', '$BACKUP_SIZE',
    'total_backups', $TOTAL_BACKUPS,
    'retention_days', $RETENTION_DAYS
));
EOF

log_success "Evento registrato nel database"

# Verifica integrità backup (opzionale)
if [ "${VERIFY_BACKUP:-false}" = "true" ]; then
    log_info "Verifica integrità backup..."
    
    # Test decompressione
    if gunzip -t "$COMPRESSED_FILE"; then
        log_success "Backup integro"
    else
        log_error "Backup corrotto!"
        exit 1
    fi
fi

log_success "Processo di backup terminato"

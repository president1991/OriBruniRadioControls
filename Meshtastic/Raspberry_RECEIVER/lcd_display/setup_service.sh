#!/bin/bash
# Script per configurare il servizio systemd per il display LCD

echo "=== Setup Servizio LCD Display ==="
echo

# Ottieni il percorso corrente
CURRENT_DIR=$(pwd)
SERVICE_FILE="lcd-display.service"
SYSTEMD_DIR="/etc/systemd/system"

# Verifica che il file di servizio esista
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ File $SERVICE_FILE non trovato!"
    exit 1
fi

# Crea una copia del file di servizio con il percorso corretto
echo "📝 Configurazione del file di servizio..."
sed "s|/home/pi/OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER/lcd_display|$CURRENT_DIR|g" "$SERVICE_FILE" > "${SERVICE_FILE}.tmp"

# Copia il file di servizio nella directory systemd
echo "📋 Copia del file di servizio in $SYSTEMD_DIR..."
sudo cp "${SERVICE_FILE}.tmp" "$SYSTEMD_DIR/$SERVICE_FILE"

# Rimuovi il file temporaneo
rm "${SERVICE_FILE}.tmp"

# Ricarica systemd
echo "🔄 Ricarica configurazione systemd..."
sudo systemctl daemon-reload

# Abilita il servizio
echo "✅ Abilitazione del servizio..."
sudo systemctl enable lcd-display.service

echo
echo "✅ Servizio configurato con successo!"
echo
echo "Comandi utili:"
echo "  Avvia servizio:    sudo systemctl start lcd-display"
echo "  Ferma servizio:    sudo systemctl stop lcd-display"
echo "  Stato servizio:    sudo systemctl status lcd-display"
echo "  Log servizio:      sudo journalctl -u lcd-display -f"
echo "  Disabilita avvio:  sudo systemctl disable lcd-display"
echo
echo "Il servizio si avvierà automaticamente al prossimo riavvio."
echo "Per avviarlo ora: sudo systemctl start lcd-display"

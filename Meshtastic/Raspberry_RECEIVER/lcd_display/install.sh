#!/bin/bash
# Script di installazione per il display LCD I2C

echo "=== Installazione Display LCD I2C per OriBruni Receiver ==="
echo

# Verifica se siamo su Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Attenzione: Questo script è progettato per Raspberry Pi"
fi

# Aggiorna il sistema
echo "📦 Aggiornamento del sistema..."
sudo apt-get update

# Installa i2c-tools se non presente
echo "🔧 Installazione i2c-tools..."
sudo apt-get install -y i2c-tools

# Installa pip se non presente
echo "🐍 Verifica installazione pip..."
sudo apt-get install -y python3-pip

# Installa le dipendenze Python
echo "📚 Installazione dipendenze Python..."
echo "Installazione tramite apt (metodo raccomandato per Raspberry Pi OS)..."
sudo apt-get install -y python3-rpi.gpio python3-smbus python3-netifaces

echo "Installazione RPLCD tramite pip con --break-system-packages..."
pip3 install --break-system-packages RPLCD==1.3.1

# Verifica se I2C è abilitato
echo "🔍 Verifica configurazione I2C..."
if ! lsmod | grep -q i2c_bcm2835; then
    echo "⚠️  I2C non sembra essere abilitato"
    echo "   Abilita I2C con: sudo raspi-config"
    echo "   Vai su: Interfacing Options -> I2C -> Enable"
    echo "   Poi riavvia il sistema"
else
    echo "✅ I2C è abilitato"
fi

# Rende eseguibili gli script
echo "🔐 Impostazione permessi..."
chmod +x lcd_display.py
chmod +x test_i2c.py

echo
echo "✅ Installazione completata!"
echo
echo "Prossimi passi:"
echo "1. Assicurati che il display LCD sia collegato correttamente:"
echo "   LCD GND  -> Raspberry Pi Pin 6  (GND)"
echo "   LCD VCC  -> Raspberry Pi Pin 2  (5V)"
echo "   LCD SDA  -> Raspberry Pi Pin 3  (GPIO 2)"
echo "   LCD SCL  -> Raspberry Pi Pin 5  (GPIO 3)"
echo
echo "2. Testa la connessione I2C:"
echo "   python3 test_i2c.py"
echo
echo "3. Avvia il display LCD:"
echo "   python3 lcd_display.py"
echo
echo "4. Per configurare come servizio:"
echo "   ./setup_service.sh"
echo

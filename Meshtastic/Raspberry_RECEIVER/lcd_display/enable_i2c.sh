#!/bin/bash
# Script per abilitare automaticamente l'I2C su Raspberry Pi

echo "=== Abilitazione I2C su Raspberry Pi ==="
echo

# Verifica se siamo su Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "❌ Questo script funziona solo su Raspberry Pi"
    exit 1
fi

echo "🔧 Abilitazione I2C nel file di configurazione..."

# Abilita I2C nel file /boot/config.txt
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
    echo "✅ I2C aggiunto a /boot/config.txt"
else
    echo "✅ I2C già abilitato in /boot/config.txt"
fi

# Abilita il modulo I2C
if ! grep -q "^i2c-dev" /etc/modules; then
    echo "i2c-dev" | sudo tee -a /etc/modules
    echo "✅ Modulo i2c-dev aggiunto a /etc/modules"
else
    echo "✅ Modulo i2c-dev già presente in /etc/modules"
fi

# Carica il modulo immediatamente
echo "🔄 Caricamento moduli I2C..."
sudo modprobe i2c-dev
sudo modprobe i2c-bcm2835

# Verifica che i moduli siano caricati
if lsmod | grep -q i2c_bcm2835; then
    echo "✅ Moduli I2C caricati correttamente"
else
    echo "⚠️  I moduli I2C potrebbero richiedere un riavvio per essere attivati"
fi

# Aggiungi l'utente al gruppo i2c
echo "👤 Aggiunta utente al gruppo i2c..."
sudo usermod -a -G i2c $USER

echo
echo "✅ Configurazione I2C completata!"
echo
echo "📋 Verifica configurazione:"
echo "   - Controlla dispositivi I2C: sudo i2cdetect -y 1"
echo "   - Se non vedi dispositivi, riavvia il sistema: sudo reboot"
echo
echo "⚠️  IMPORTANTE: Se hai appena abilitato l'I2C, riavvia il sistema:"
echo "   sudo reboot"
echo

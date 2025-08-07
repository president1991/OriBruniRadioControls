#!/bin/bash

# Script per l'installazione e la configurazione completa dell'ambiente
# per OriBruni Raspberry RECEIVER su un Raspberry Pi.

set -e

echo "================================================="
echo "Inizio installazione ambiente OriBruni Receiver"
echo "================================================="

# 1. Aggiornamento del sistema
echo "--> 1/6: Aggiornamento del sistema..."
sudo apt update && sudo apt upgrade -y

# 2. Installazione dipendenze di sistema
echo "--> 2/6: Installazione dipendenze di sistema..."
sudo apt install -y python3-pip python3-dev python3-venv git i2c-tools python3-smbus apache2 mariadb-server php php-mysql phpmyadmin

# 3. Configurazione MariaDB
echo "--> 3/6: Configurazione di MariaDB..."
sudo mysql_secure_installation

echo "Creazione database e utente..."
sudo mysql -u root -pPuhA7gWCrW <<MYSQL_SCRIPT
CREATE DATABASE IF NOT EXISTS OriBruniRadioControls;
CREATE USER IF NOT EXISTS 'meshdash'@'localhost' IDENTIFIED BY 'PuhA7gWCrW';
GRANT ALL PRIVILEGES ON OriBruniRadioControls.* TO 'meshdash'@'localhost';
FLUSH PRIVILEGES;
MYSQL_SCRIPT
echo "Database e utente creati. La password per 'meshdash' è 'PuhA7gWCrW'."
echo "Assicurati di aggiornare il file config.ini con questa password."

# 4. Configurazione del progetto Python
echo "--> 4/6: Configurazione del progetto Python..."
cd /home/radiocontrol/RECEIVER
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# 5. Installazione servizi systemd
echo "--> 5/6: Installazione dei servizi systemd..."
cd services
sudo bash install_services.sh
cd ..

# 6. Configurazione phpMyAdmin
echo "--> 6/6: Configurazione di phpMyAdmin..."
sudo ln -s /usr/share/phpmyadmin /var/www/html/phpmyadmin
echo "phpMyAdmin configurato. Accedi a http://<IP_RASPBERRY>/phpmyadmin"

echo "================================================="
echo "Installazione completata!"
echo "Riavvia il Raspberry Pi per applicare tutte le modifiche."
echo "sudo reboot"
echo "================================================="

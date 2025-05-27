# OriBruni Raspberry RECEIVER

Sistema completo per ricevere e gestire dati da dispositivi Meshtastic, specificamente progettato per il controllo radio in eventi di orienteering.

## 🚀 Caratteristiche Principali

- **Interfaccia Web Real-time**: Visualizzazione grafica della rete mesh con aggiornamenti WebSocket
- **Database MySQL**: Archiviazione persistente di messaggi e punzonature
- **Display LCD**: Monitoraggio locale su display I2C 20x4
- **API REST**: Esportazione dati in formato CSV
- **Auto-discovery**: Rilevamento automatico dispositivi Meshtastic
- **Backup Automatico**: Script di backup giornaliero del database
- **Servizi Systemd**: Avvio automatico e gestione processi

## 📋 Requisiti Hardware

### Minimo
- Raspberry Pi 4 (4GB RAM)
- MicroSD 32GB Classe 10
- Dispositivo Meshtastic (LoRa)
- Display LCD I2C 20x4 (opzionale)

### Consigliato
- Raspberry Pi 4 (8GB RAM)
- MicroSD 64GB Classe 10 A2
- Case con ventola
- Alimentatore ufficiale 5V 3A

## 🛠️ Installazione Rapida

### Metodo 1: Script Automatico (Consigliato)

```bash
# Clona il repository
git clone https://github.com/your-repo/OriBruniRadioControls.git
cd OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER

# Rendi eseguibile lo script di installazione
chmod +x install.sh

# Esegui l'installazione (richiede sudo)
sudo ./install.sh

# Riavvia il sistema
sudo reboot
```

### Metodo 2: Installazione Manuale

#### 1. Aggiorna il sistema
```bash
sudo apt update && sudo apt upgrade -y
```

#### 2. Installa dipendenze di sistema
```bash
sudo apt install -y python3 python3-pip python3-dev python3-venv \
    build-essential libmariadb-dev pkg-config i2c-tools python3-smbus \
    git curl wget mariadb-server mariadb-client nginx
```

#### 3. Abilita I2C (per display LCD)
```bash
sudo raspi-config
# Interfacing Options -> I2C -> Enable
# Oppure:
echo 'dtparam=i2c_arm=on' | sudo tee -a /boot/config.txt
```

#### 4. Configura database
```bash
sudo mysql_secure_installation
sudo mysql -u root -p
```

```sql
CREATE DATABASE OriBruniRadioControls;
CREATE USER 'meshdash'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON OriBruniRadioControls.* TO 'meshdash'@'localhost';
FLUSH PRIVILEGES;
```

#### 5. Installa applicazione Python
```bash
# Crea directory applicazione
sudo mkdir -p /opt/oribruni-receiver
cd /opt/oribruni-receiver

# Copia file progetto
sudo cp -r /path/to/Raspberry_RECEIVER/* .

# Crea ambiente virtuale
python3 -m venv venv
source venv/bin/activate

# Installa dipendenze Python
pip install --upgrade pip
pip install -r requirements.txt
```

## ⚙️ Configurazione

### File di Configurazione (`config.ini`)

```ini
[serial]
port = auto  # Auto-detection o specifica porta (es. COM3, /dev/ttyUSB0)

[app]
log_file = meshdash.log
refresh_interval = 10000  # ms
log_level = INFO

[mysql]
host = localhost
port = 3306
user = meshdash
password = your_password
database = OriBruniRadioControls
autocommit = True
```

### Configurazione Porta Seriale

Il sistema rileva automaticamente i dispositivi Meshtastic collegati. Se necessario, specifica manualmente la porta nel file `config.ini`:

**Windows:**
```ini
port = COM3
```

**Linux/Raspberry Pi:**
```ini
port = /dev/ttyUSB0
```

## 🚀 Utilizzo

### Avvio Manuale
```bash
cd /opt/oribruni-receiver
source venv/bin/activate
python server.py
```

### Servizi Systemd (Installazione Automatica)
```bash
# Stato servizi
sudo systemctl status oribruni-receiver
sudo systemctl status oribruni-lcd

# Avvio/Stop servizi
sudo systemctl start oribruni-receiver
sudo systemctl stop oribruni-receiver

# Logs
sudo journalctl -u oribruni-receiver -f
sudo journalctl -u oribruni-lcd -f
```

### Accesso Web Interface

Dopo l'installazione, l'interfaccia web è disponibile su:
- **URL**: `http://[IP_RASPBERRY_PI]`
- **Porta**: 80 (tramite Nginx proxy)

## 📊 Interfaccia Web

### Dashboard Principale
- **Visualizzazione Rete**: Grafico interattivo della rete mesh
- **Lista Dispositivi**: Stato batteria e informazioni nodi
- **Aggiornamenti Real-time**: WebSocket per dati live

### Esportazione Dati
- **Filtri**: Unit ID, Last ID, Data/Ora
- **Formato**: CSV per integrazione con sistemi esterni
- **API Endpoint**: `/export_punches`

## 🗄️ Struttura Database

### Tabella `messages`
Archivia tutti i messaggi ricevuti dalla rete Meshtastic:
- `id`: Chiave primaria auto-incrementale
- `timestamp`: Data/ora ricezione messaggio
- `node_eui`: Identificativo nodo mittente
- `field1`, `field2`, `field3`: Campi dati del messaggio
- `raw`: Messaggio completo non processato

### Tabella `punches`
Archivia specificamente le punzonature per orienteering:
- `id`: Chiave primaria auto-incrementale
- `timestamp`: Data/ora ricezione
- `name`: Nome dispositivo
- `record_id`: ID record punzonatura
- `control`: Codice controllo
- `card_number`: Numero chip/card
- `punch_time`: Orario punzonatura
- `raw`: Dati completi non processati

## 🔧 Manutenzione

### Backup Database
```bash
# Backup manuale
/opt/oribruni-receiver/backup.sh

# I backup automatici vengono eseguiti ogni notte alle 02:00
# Posizione: /opt/oribruni-receiver/backups/
```

### Monitoraggio Sistema
```bash
# Stato servizi
sudo systemctl status oribruni-receiver oribruni-lcd

# Utilizzo risorse
htop
df -h
free -h

# Test connessione database
mysql -u meshdash -p OriBruniRadioControls
```

### Logs e Debugging
```bash
# Logs applicazione
sudo journalctl -u oribruni-receiver -f

# Logs LCD display
sudo journalctl -u oribruni-lcd -f

# Logs Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Test I2C (per LCD)
sudo i2cdetect -y 1
```

## 🔒 Sicurezza

### Firewall (UFW)
```bash
sudo ufw status
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### Database Security
- Utente dedicato con privilegi limitati
- Password complesse
- Accesso solo da localhost

### Aggiornamenti Sistema
```bash
# Aggiornamenti automatici
sudo apt update && sudo apt upgrade -y

# Aggiornamenti Python packages
source /opt/oribruni-receiver/venv/bin/activate
pip list --outdated
pip install --upgrade package_name
```

## 🐛 Risoluzione Problemi

### Dispositivo Meshtastic Non Rilevato
```bash
# Verifica dispositivi USB
lsusb
ls -la /dev/ttyUSB*
ls -la /dev/serial/by-id/

# Permessi porta seriale
sudo usermod -a -G dialout pi
sudo chmod 666 /dev/ttyUSB0
```

### Errori Database
```bash
# Test connessione
mysql -u meshdash -p OriBruniRadioControls

# Verifica tabelle
SHOW TABLES;
DESCRIBE messages;
DESCRIBE punches;
```

### Display LCD Non Funziona
```bash
# Test I2C
sudo i2cdetect -y 1

# Verifica moduli
lsmod | grep i2c

# Carica moduli manualmente
sudo modprobe i2c-dev
sudo modprobe i2c-bcm2835
```

### Servizi Non Partono
```bash
# Verifica configurazione
sudo systemctl status oribruni-receiver
sudo journalctl -u oribruni-receiver --no-pager

# Reset servizi
sudo systemctl daemon-reload
sudo systemctl restart oribruni-receiver
```

## 📚 API Reference

### GET `/export_punches`

Esporta dati punzonature in formato CSV.

**Parametri:**
- `unitId` (int): ID unità (default: 0)
- `lastId` (int): Ultimo ID processato (default: 0)
- `date` (string): Data filtro (formato: YYYY-MM-DD)
- `time` (string): Ora filtro (formato: HH:MM:SS)

**Esempio:**
```
GET /export_punches?unitId=1&lastId=100&date=2025-05-27&time=10:00:00
```

**Risposta:**
```
1;31;1234567;2025-05-27 10:15:30
2;32;1234567;2025-05-27 10:18:45
```

## 🤝 Contribuire

1. Fork del repository
2. Crea branch feature (`git checkout -b feature/AmazingFeature`)
3. Commit modifiche (`git commit -m 'Add AmazingFeature'`)
4. Push branch (`git push origin feature/AmazingFeature`)
5. Apri Pull Request

## 📄 Licenza

Questo progetto è distribuito sotto licenza MIT. Vedi `LICENSE` per dettagli.

## 📞 Supporto

Per supporto tecnico:
- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Email**: support@oribruni.com
- **Documentazione**: [Wiki del progetto](https://github.com/your-repo/wiki)

---

**OriBruni Radio Controls** - Sistema professionale per controllo radio eventi di orienteering

# 🚀 Installazione Rapida OriBruni Receiver Docker

Guida step-by-step per installare il sistema OriBruni Receiver con Docker su Raspberry Pi.

## 📋 Prerequisiti

- **Raspberry Pi 4** (4GB+ RAM consigliato)
- **MicroSD 32GB+** con Raspberry Pi OS
- **Dispositivo Meshtastic** collegato via USB
- **Connessione Internet**

## ⚡ Installazione in 5 Passi

### 1️⃣ Copia i File del Progetto

Sul Raspberry Pi, copia tutti i file del progetto in una directory:

```bash
# Crea directory di lavoro
mkdir ~/oribruni-receiver
cd ~/oribruni-receiver

# Copia qui tutti i file del progetto OriBruni Receiver
# (Dockerfile, docker-compose.yml, config.ini, ecc.)
```

### 2️⃣ Esegui lo Script di Installazione

```bash
# Rendi eseguibile lo script
chmod +x install-docker.sh

# Esegui l'installazione
./install-docker.sh
```

Lo script installerà automaticamente:
- ✅ Docker Engine
- ✅ Docker Compose
- ✅ Configurazione I2C per LCD
- ✅ Struttura directory
- ✅ Permessi corretti

### 3️⃣ Riavvia il Sistema

```bash
sudo reboot
```

**IMPORTANTE**: Il riavvio è necessario per applicare i permessi Docker e I2C.

### 4️⃣ Avvia i Servizi

Dopo il riavvio:

```bash
cd ~/oribruni-receiver

# Avvia tutti i servizi
make up

# Oppure usa Docker Compose direttamente
docker compose up -d
```

### 5️⃣ Verifica Installazione

```bash
# Controlla stato servizi
make status

# Visualizza logs
make logs

# Test salute sistema
make health
```

## 🌐 Accesso al Sistema

Una volta avviato, il sistema sarà disponibile su:

- **🖥️ Interfaccia Web**: `http://[IP_RASPBERRY]`
- **🗄️ phpMyAdmin**: `http://[IP_RASPBERRY]:8080/phpmyadmin`
- **📊 Database**: `[IP_RASPBERRY]:3306`

### Trova l'IP del Raspberry Pi:
```bash
hostname -I
```

## 🔑 Credenziali Database

- **Root**: `root` / `PuhA7gWCrW`
- **Applicazione**: `meshdash` / `MeshDash2025!`

## 📱 Comandi Utili

```bash
# Mostra tutti i comandi disponibili
make help

# Avvia/ferma servizi
make up
make down

# Logs in tempo reale
make logs

# Backup database
make db-backup

# Stato servizi
make status

# Accesso shell applicazione
make shell

# Pulizia sistema
make clean
```

## 🔧 Configurazione Dispositivo Meshtastic

1. **Collega il dispositivo Meshtastic** via USB al Raspberry Pi
2. **Verifica rilevamento**:
   ```bash
   lsusb
   ls /dev/ttyUSB*
   ```
3. Il sistema rileverà automaticamente il dispositivo

## 📺 Display LCD (Opzionale)

Se hai un display LCD I2C 20x4:

1. **Collega il display** ai pin I2C del Raspberry Pi
2. **Verifica connessione**:
   ```bash
   sudo i2cdetect -y 1
   ```
3. **Avvia servizio LCD**:
   ```bash
   make up-full
   ```

## 🆘 Risoluzione Problemi

### Container non si avvia
```bash
make logs-app
docker compose config
```

### Database non raggiungibile
```bash
make logs-db
docker compose exec mysql mysqladmin ping -u root -pPuhA7gWCrW
```

### Dispositivo Meshtastic non rilevato
```bash
lsusb
sudo dmesg | grep tty
```

### Display LCD non funziona
```bash
sudo i2cdetect -y 1
make logs-lcd
```

## 🔄 Aggiornamenti

```bash
# Aggiorna immagini Docker
make update

# Rebuild completo
make rebuild
```

## 💾 Backup

```bash
# Backup automatico database
make db-backup

# Backup completo sistema
make down
sudo tar -czf backup_$(date +%Y%m%d).tar.gz ~/oribruni-receiver/
```

## 📞 Supporto

Se hai problemi:

1. **Controlla logs**: `make logs`
2. **Verifica stato**: `make health`
3. **Salva logs per debug**: `make logs > debug.txt`

---

## 🎯 Installazione Alternativa (Manuale)

Se preferisci installare manualmente:

### Installa Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
sudo apt install -y docker-compose-plugin
sudo reboot
```

### Setup Progetto
```bash
mkdir ~/oribruni-receiver
cd ~/oribruni-receiver
# Copia file progetto qui
mkdir -p {data/mysql,logs/nginx,backups,nginx/ssl}
chmod +x scripts/backup.sh
```

### Avvia Servizi
```bash
docker compose up -d
```

---

**🎉 Installazione Completata!**

Il tuo sistema OriBruni Receiver è ora pronto per gestire eventi di orienteering con tecnologia Meshtastic.

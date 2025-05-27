# 🚀 Installazione OriBruni Receiver Docker da GitHub

## ⚡ Installazione Ultra-Rapida (3 Comandi)

Sul tuo Raspberry Pi, esegui questi comandi per installare tutto automaticamente:

```bash
# 1. Installa Git (se non presente)
sudo apt update && sudo apt install -y git

# 2. Clona repository e vai nella directory
git clone https://github.com/president1991/OriBruniRadioControls.git
cd OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER

# 3. Esegui installazione automatica
chmod +x install-docker.sh && ./install-docker.sh
```

### Cosa fanno questi comandi:
1. ✅ Installa Git per clonare il repository
2. ✅ Clona il repository OriBruni da GitHub
3. ✅ Installa Docker e Docker Compose
4. ✅ Configura I2C per display LCD
5. ✅ Crea struttura directory ottimizzata
6. ✅ Imposta permessi corretti
7. ✅ Prepara tutto per l'avvio

### Dopo l'installazione:
```bash
# Riavvia il sistema
sudo reboot

# Dopo il riavvio, vai nella directory e avvia
cd ~/oribruni-receiver
make up
```

---

## 🔧 Installazione Passo-Passo (se preferisci)

### Passo 0: Installa Git
```bash
sudo apt update && sudo apt install -y git
```

### Passo 1: Clona Repository
```bash
git clone https://github.com/president1991/OriBruniRadioControls.git
cd OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER
```

### Passo 2: Esegui Installazione
```bash
chmod +x install-docker.sh
./install-docker.sh
```

### Passo 3: Riavvia Sistema
```bash
sudo reboot
```

### Passo 4: Avvia Servizi
```bash
cd ~/oribruni-receiver
make up
```

### Passo 5: Verifica Installazione
```bash
make status
make health
```

---

## 🌐 Accesso Sistema

Dopo l'avvio, il sistema sarà disponibile su:

- **🖥️ Interfaccia Web**: `http://[IP_RASPBERRY]`
- **🗄️ phpMyAdmin**: `http://[IP_RASPBERRY]:8080/phpmyadmin`
- **📊 Database**: `[IP_RASPBERRY]:3306`

### Trova IP Raspberry Pi:
```bash
hostname -I
```

### Credenziali Database:
- **Root**: `root` / `PuhA7gWCrW`
- **App**: `meshdash` / `MeshDash2025!`

---

## 📱 Comandi Utili

```bash
make help          # Mostra tutti i comandi disponibili
make up            # Avvia tutti i servizi
make down          # Ferma tutti i servizi
make restart       # Riavvia servizi
make status        # Stato servizi
make logs          # Logs in tempo reale
make db-backup     # Backup database
make health        # Verifica sistema
make shell         # Accesso shell applicazione
make clean         # Pulizia sistema
```

---

## 🔧 Configurazione Dispositivo Meshtastic

1. **Collega il dispositivo Meshtastic** via USB al Raspberry Pi
2. **Verifica rilevamento**:
   ```bash
   lsusb
   ls /dev/ttyUSB*
   ```
3. Il sistema rileverà automaticamente il dispositivo

---

## 📺 Display LCD (Opzionale)

Se hai un display LCD I2C 20x4:

1. **Collega il display** ai pin I2C del Raspberry Pi:
   - VCC → 5V (Pin 2)
   - GND → GND (Pin 6)
   - SDA → GPIO 2 (Pin 3)
   - SCL → GPIO 3 (Pin 5)

2. **Verifica connessione**:
   ```bash
   sudo i2cdetect -y 1
   ```

3. **Avvia con LCD**:
   ```bash
   make up-full
   ```

---

## 🆘 Risoluzione Problemi

### Git non trovato
```bash
sudo apt update && sudo apt install -y git
```

### Container non si avvia
```bash
make logs-app
docker compose config
make rebuild
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
# Riavvia container con privilegi
make down && make up
```

### Display LCD non funziona
```bash
sudo i2cdetect -y 1
make logs-lcd
```

### Errore permessi Docker
```bash
sudo usermod -aG docker $USER
sudo reboot
```

---

## 🔄 Aggiornamenti

```bash
# Aggiorna repository
cd ~/OriBruniRadioControls
git pull

# Aggiorna sistema Docker
cd ~/oribruni-receiver
make update
```

---

## 💾 Backup e Restore

### Backup Automatico
Il sistema esegue backup automatici ogni notte alle 02:00.

### Backup Manuale
```bash
make db-backup
```

### Backup Completo Sistema
```bash
make down
sudo tar -czf backup_$(date +%Y%m%d).tar.gz ~/oribruni-receiver/
```

### Restore Database
```bash
make db-restore BACKUP_FILE=backups/oribruni_backup_YYYYMMDD_HHMMSS.sql.gz
```

---

## 📊 Monitoraggio

### Stato Servizi
```bash
make status
make health
```

### Logs in Tempo Reale
```bash
make logs           # Tutti i servizi
make logs-app       # Solo applicazione
make logs-db        # Solo database
make logs-nginx     # Solo nginx
```

### Utilizzo Risorse
```bash
docker stats
```

---

## 🎯 Requisiti Sistema

### Hardware Minimo:
- **Raspberry Pi 4** (4GB+ RAM consigliato)
- **MicroSD 32GB+** Classe 10
- **Dispositivo Meshtastic** USB
- **Display LCD I2C 20x4** (opzionale)

### Software:
- **Raspberry Pi OS** (64-bit consigliato)
- **Connessione Internet** per installazione

---

## 📞 Supporto

Se hai problemi:

1. **Controlla logs**: `make logs`
2. **Verifica stato**: `make health`
3. **Salva logs per debug**: `make logs > debug.txt`
4. **Test connettività**: `make test`

### File di Log Utili:
- `~/oribruni-receiver/logs/meshdash.log`
- `~/oribruni-receiver/logs/nginx/access.log`
- `~/oribruni-receiver/logs/nginx/error.log`

---

## 🚀 Installazione One-Liner Completa

Se vuoi fare tutto in un comando:

```bash
sudo apt update && sudo apt install -y git && git clone https://github.com/president1991/OriBruniRadioControls.git && cd OriBruniRadioControls/Meshtastic/Raspberry_RECEIVER && chmod +x install-docker.sh && ./install-docker.sh
```

Poi riavvia e avvia:
```bash
sudo reboot
cd ~/oribruni-receiver
make up
```

---

**🎉 Installazione completata!**

Il sistema OriBruni Receiver Docker è ora pronto per gestire eventi di orienteering con tecnologia Meshtastic.

### Prossimi Passi:
1. Collega dispositivo Meshtastic
2. Configura evento nell'interfaccia web
3. Testa ricezione punzonature
4. Configura backup automatici

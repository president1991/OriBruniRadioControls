# 🚀 Installazione One-Liner OriBruni Receiver Docker

## ⚡ Installazione Ultra-Rapida (1 Comando)

Sul tuo Raspberry Pi, esegui questo singolo comando per installare tutto automaticamente:

```bash
curl -fsSL https://raw.githubusercontent.com/president1991/OriBruniRadioControls/main/Meshtastic/Raspberry_RECEIVER/install-docker.sh | bash
```

### Cosa fa questo comando:
1. ✅ Scarica lo script di installazione da GitHub
2. ✅ Installa Docker e Docker Compose
3. ✅ Clona il repository OriBruni
4. ✅ Configura I2C per display LCD
5. ✅ Crea struttura directory
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

## 🔧 Installazione Manuale (se preferisci)

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

### Passo 3: Riavvia e Avvia
```bash
sudo reboot
cd ~/oribruni-receiver
make up
```

---

## 🌐 Accesso Sistema

Dopo l'avvio, il sistema sarà disponibile su:

- **🖥️ Interfaccia Web**: `http://[IP_RASPBERRY]`
- **🗄️ phpMyAdmin**: `http://[IP_RASPBERRY]:8080/phpmyadmin`

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
make help          # Mostra tutti i comandi
make status        # Stato servizi
make logs          # Logs in tempo reale
make db-backup     # Backup database
make health        # Verifica sistema
```

---

## 🎯 Requisiti Minimi

- **Raspberry Pi 4** (4GB+ RAM)
- **MicroSD 32GB+** con Raspberry Pi OS
- **Connessione Internet**
- **Dispositivo Meshtastic** USB

---

**🎉 Installazione completata in 1 comando!**

Il sistema OriBruni Receiver Docker è ora pronto per gestire eventi di orienteering con tecnologia Meshtastic.

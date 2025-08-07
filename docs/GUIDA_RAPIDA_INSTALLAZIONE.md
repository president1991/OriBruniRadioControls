# 🚀 GUIDA RAPIDA - Installazione OriBruniRadioControls

## ✅ Procedura Completa in 5 Minuti

### 1️⃣ **Prepara Raspberry Pi**
```bash
# Installa Raspberry Pi OS (Lite o Desktop)
# Abilita SSH se necessario
# Connetti a Internet (WiFi o Ethernet)
# Login come utente 'pi' (NON root!)
```

### 2️⃣ **Scarica i File**
```bash
# Opzione A: Git (se disponibile)
git clone https://github.com/president1991/OriBruniRadioControls.git
cd OriBruniRadioControls

# Opzione B: Download ZIP e copia su Raspberry Pi
# - Scarica ZIP da GitHub
# - Copia su Raspberry Pi via SCP/USB
# - Estrai: unzip OriBruniRadioControls-main.zip
# - cd OriBruniRadioControls-main
```

### 3️⃣ **Collega Hardware**

#### Per LETTORE:
- **Qualsiasi porta USB**: Adattatore seriale SportIdent (baudrate 38400)
- **Qualsiasi porta USB**: Adattatore seriale Meshtastic (baudrate 115200)
- **I2C**: Display OLED 0.96" → SDA/SCL (pin 3/5)

#### Per RICEVITORE:
- **Qualsiasi porta USB**: Adattatore seriale Meshtastic (baudrate 115200)
- **Ethernet/WiFi**: Connessione Internet

> **📌 IMPORTANTE**: Il sistema rileva automaticamente le porte! Non importa quale USB usi, il software riconosce i dispositivi dal baudrate e dai dati che inviano.

#### 🔍 **Come Funziona il Rilevamento Automatico:**
1. **All'avvio**, il sistema scansiona tutte le porte `/dev/ttyUSB*` e `/dev/ttyACM*`
2. **Testa ogni porta** con diversi baudrate (38400 per SportIdent, 115200 per Meshtastic)
3. **Riconosce il dispositivo** dai dati che riceve:
   - SportIdent invia dati con formato specifico delle punzonature
   - Meshtastic invia messaggi mesh con header riconoscibili
4. **Assegna automaticamente** la porta corretta a ogni servizio

**Esempio**: Se colleghi SportIdent alla seconda USB e Meshtastic alla prima, il sistema li trova comunque!

### 4️⃣ **Avvia Deploy Automatico**

#### Per LETTORE:
```bash
python3 deploy_raspberry.py reader reader-01 --auto-start
```

#### Per RICEVITORE:
```bash
python3 deploy_raspberry.py receiver receiver-main --auto-start
```

### 5️⃣ **Verifica Funzionamento**
```bash
# Controlla servizi
systemctl status oribruni-*

# Controlla log
journalctl -f -u oribruni-*

# Health check
./health_check.sh
```

---

## 🔧 Cosa Fa il Deploy Automaticamente

### ✅ **Sistema**
- Aggiorna pacchetti sistema
- Installa dipendenze (Python, I2C tools, MySQL client, etc.)
- Configura I2C e GPIO
- Crea utenti e permessi

### ✅ **Python**
- Crea ambiente virtuale
- Installa tutte le librerie necessarie
- Configura OLED display libraries

### ✅ **Servizi**
- Crea servizi systemd personalizzati
- Configura avvio automatico
- Setup logging e monitoraggio

### ✅ **Configurazione**
- File configurazione dispositivo
- Script di avvio e manutenzione
- Cron jobs per backup e health check

---

## 🎯 Risultato Finale

### **LETTORE Pronto:**
- ✅ Legge SportIdent automaticamente
- ✅ Trasmette via Meshtastic
- ✅ Display OLED mostra status
- ✅ Sincronizzazione temporale attiva
- ✅ Servizi avviati automaticamente

### **RICEVITORE Pronto:**
- ✅ Riceve da Meshtastic e Internet
- ✅ Database MySQL configurato
- ✅ API `/getpunches` attiva
- ✅ Dashboard web disponibile
- ✅ Server time sync attivo

---

## 🚨 Se Qualcosa Non Funziona

### **Errore Porte Seriali:**
```bash
# Verifica porte disponibili
ls -la /dev/ttyUSB*

# Se non ci sono, controlla connessioni USB
dmesg | tail -20
```

### **Errore Display OLED:**
```bash
# Verifica I2C
i2cdetect -y 1
# Deve mostrare dispositivo su indirizzo 3c o 3d
```

### **Errore Permessi:**
```bash
# Assicurati di NON essere root
whoami
# Deve mostrare: pi

# Se sei root, cambia utente:
su - pi
```

### **Log Dettagliati:**
```bash
# Vedi cosa sta succedendo
tail -f logs/deploy.log

# Log servizi
journalctl -u oribruni-sportident -f
```

---

## 📞 Supporto Rapido

### **Test Hardware:**
```bash
# Test porte seriali
python3 -c "
import serial
try:
    ser = serial.Serial('/dev/ttyUSB0', 38400, timeout=1)
    print('✅ SportIdent OK')
    ser.close()
except:
    print('❌ SportIdent ERRORE')

try:
    ser = serial.Serial('/dev/ttyUSB1', 115200, timeout=1)
    print('✅ Meshtastic OK')
    ser.close()
except:
    print('❌ Meshtastic ERRORE')
"

# Test display OLED
python3 oled_display.py --device-name test --demo
```

### **Riavvio Completo:**
```bash
# Se qualcosa va storto, riavvia tutto
sudo systemctl stop oribruni-*
sudo systemctl start oribruni-*

# Oppure riavvia Raspberry Pi
sudo reboot
```

---

## 🎉 Pronto per l'Evento!

Una volta completato il deploy:

1. **LETTORI**: Collegare SportIdent e Meshtastic, il display mostrerà lo status
2. **RICEVITORI**: Aprire browser su `http://IP_RASPBERRY:8000` per dashboard
3. **Monitoraggio**: Usare `./health_check.sh` per controlli periodici

**Il sistema è ora completamente automatico e pronto per eventi di orienteering!** 🏃‍♂️🧭

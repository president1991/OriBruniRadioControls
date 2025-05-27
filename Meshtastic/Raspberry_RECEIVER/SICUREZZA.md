# 🔒 SICUREZZA - OriBruni Receiver Docker

## 🚨 PROBLEMI DI SICUREZZA IDENTIFICATI

Hai reso pubblica la repository e ci sono **problemi di sicurezza critici** che devi risolvere immediatamente:

### ❌ Password Hardcoded Esposte

**File con password in chiaro:**
- `docker-compose.yml` - Password MySQL visibili
- `config.ini` - Credenziali database esposte
- `install-docker.sh` - Password hardcoded nello script

**Password esposte pubblicamente:**
- `MYSQL_ROOT_PASSWORD: PuhA7gWCrW`
- `MYSQL_PASSWORD: MeshDash2025!`

## ✅ SOLUZIONI IMPLEMENTATE

Ho risolto i problemi di sicurezza creando:

### 1. File `.env.example` (Template Sicuro)
```bash
# File template con password placeholder
MYSQL_ROOT_PASSWORD=CAMBIA_QUESTA_PASSWORD_ROOT
MYSQL_PASSWORD=CAMBIA_QUESTA_PASSWORD_USER
```

### 2. File `.gitignore` (Protezione File Sensibili)
```bash
# Protegge file con password
.env
config.ini
data/
logs/
backups/
```

### 3. `docker-compose.yml` Aggiornato (Variabili d'Ambiente)
```yaml
# Ora usa variabili sicure
MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
MYSQL_PASSWORD: ${MYSQL_PASSWORD}
```

## 🛠️ AZIONI IMMEDIATE RICHIESTE

### 1. Rimuovi File Sensibili dal Repository
```bash
# Rimuovi file con password dal tracking Git
git rm --cached Meshtastic/Raspberry_RECEIVER/config.ini
git commit -m "Remove sensitive config file"
git push
```

### 2. Aggiorna .gitignore
Il file `.gitignore` è già stato creato e proteggerà:
- File `.env` con password
- Directory `data/`, `logs/`, `backups/`
- Certificati SSL
- File temporanei

### 3. Cambia Tutte le Password
**IMPORTANTE**: Le password esposte sono compromesse!

```bash
# Genera password sicure
openssl rand -base64 32
```

### 4. Usa il Nuovo Sistema Sicuro
```bash
# Copia template e configura password
cp .env.example .env
nano .env  # Inserisci password sicure
```

## 🔐 CONFIGURAZIONE SICURA

### Passo 1: Crea File .env
```bash
cd ~/oribruni-receiver
cp .env.example .env
```

### Passo 2: Genera Password Sicure
```bash
# Genera password root
echo "MYSQL_ROOT_PASSWORD=$(openssl rand -base64 32)"

# Genera password utente
echo "MYSQL_PASSWORD=$(openssl rand -base64 32)"
```

### Passo 3: Configura .env
```bash
nano .env
```

Inserisci:
```env
MYSQL_ROOT_PASSWORD=TuaPasswordRootSicura123!
MYSQL_PASSWORD=TuaPasswordUserSicura456!
MYSQL_DATABASE=OriBruniRadioControls
MYSQL_USER=meshdash
FLASK_ENV=production
LOG_LEVEL=INFO
RETENTION_DAYS=30
VERIFY_BACKUP=false
```

### Passo 4: Avvia Sistema Sicuro
```bash
docker compose up -d
```

## 🛡️ BEST PRACTICES SICUREZZA

### 1. Password
- ✅ **Usa password complesse** (32+ caratteri)
- ✅ **Password uniche** per ogni servizio
- ✅ **Genera con openssl** o password manager
- ❌ **Mai password hardcoded** nel codice

### 2. File Sensibili
- ✅ **Sempre nel .gitignore**
- ✅ **File .env locali** non committati
- ✅ **Template .env.example** pubblici
- ❌ **Mai credenziali** nel repository

### 3. Accesso Database
- ✅ **Porta 3306 solo locale** (127.0.0.1:3306)
- ✅ **Firewall configurato**
- ✅ **Accesso limitato** agli IP necessari
- ❌ **Mai database pubblico** su internet

### 4. SSL/TLS
- ✅ **Certificati SSL** per HTTPS
- ✅ **Nginx reverse proxy** configurato
- ✅ **Redirect HTTP → HTTPS**
- ❌ **Mai traffico non crittografato**

## 🚨 AZIONI IMMEDIATE DA FARE

### 1. **SUBITO** - Rimuovi Password dal Git
```bash
# Vai nella directory del repository
cd ~/OriBruniRadioControls

# Rimuovi file sensibili dal tracking
git rm --cached Meshtastic/Raspberry_RECEIVER/config.ini

# Commit e push
git add .
git commit -m "🔒 Security: Remove hardcoded passwords, add .env system"
git push
```

### 2. **SUBITO** - Cambia Password Database
Se hai già installato il sistema con le password esposte:

```bash
# Ferma servizi
cd ~/oribruni-receiver
make down

# Crea .env con password nuove
cp .env.example .env
nano .env  # Inserisci password sicure

# Rimuovi dati vecchi
sudo rm -rf data/mysql/*

# Riavvia con password nuove
make up
```

### 3. **SUBITO** - Configura Firewall
```bash
# Installa UFW
sudo apt install ufw

# Blocca tutto di default
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Permetti solo SSH e HTTP/HTTPS
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443

# Abilita firewall
sudo ufw enable
```

## 📋 CHECKLIST SICUREZZA

- [ ] ✅ File `.gitignore` creato
- [ ] ✅ File `.env.example` creato  
- [ ] ✅ `docker-compose.yml` usa variabili d'ambiente
- [ ] ❌ **DA FARE**: Rimuovi `config.ini` dal Git
- [ ] ❌ **DA FARE**: Cambia tutte le password
- [ ] ❌ **DA FARE**: Configura firewall
- [ ] ❌ **DA FARE**: Testa sistema con password nuove

## 🆘 Se Hai Problemi

1. **Backup dati** prima di cambiare password
2. **Testa in locale** prima di deployare
3. **Documenta password** in password manager sicuro
4. **Non condividere** file `.env` mai

---

**⚠️ IMPORTANTE**: Le password esposte pubblicamente sono compromesse e devono essere cambiate immediatamente!

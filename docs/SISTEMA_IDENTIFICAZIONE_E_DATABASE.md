# 🔐 Sistema di Identificazione e Database Remoto

## 🎯 **Come Funziona l'Identificazione dei Dispositivi**

### **📋 Tabella `costanti` - Identità Dispositivo**

Ogni Raspberry Pi ha una **identità univoca** memorizzata nella tabella `costanti` del database locale:

```sql
CREATE TABLE costanti (
    nome VARCHAR(50) PRIMARY KEY,
    valore TEXT NOT NULL
);

-- Esempio dati per un lettore:
INSERT INTO costanti VALUES ('nome', 'reader-01');
INSERT INTO costanti VALUES ('pkey', 'abc123def456ghi789jkl012mno345pqr678stu901vwx234yz');
```

### **🔑 Campi Identificativi:**

- **`nome`**: Nome leggibile del dispositivo (es: `reader-01`, `receiver-main`)
- **`pkey`**: Chiave privata univoca di 48+ caratteri alfanumerici

## 🌐 **Invio Dati al Database Remoto**

### **📤 Processo di Invio (`send_data_internet.py`)**

1. **Lettura Punzonature Locali**:
   ```sql
   SELECT * FROM radiocontrol WHERE sent_internet = 0
   ```

2. **Aggiunta Identità Dispositivo**:
   ```python
   # Per ogni punzonatura da inviare:
   record_to_send = record.copy()
   record_to_send['name'] = device_name      # es: "reader-01"
   record_to_send['pkey'] = device_pkey      # es: "abc123def..."
   ```

3. **Invio HTTP POST**:
   ```python
   # Endpoint remoto
   REMOTE_URL = "https://orienteering.services/radiocontrol/receive_data.php"
   
   # Payload JSON con identità
   {
       "id": 123,
       "control": "31",
       "card_number": "12345",
       "punch_time": "2025-01-07T10:30:15",
       "timestamp": "2025-01-07T10:30:16",
       "name": "reader-01",           # ← IDENTITÀ DISPOSITIVO
       "pkey": "abc123def456..."      # ← CHIAVE PRIVATA
   }
   ```

4. **Conferma Invio**:
   ```sql
   -- Se server risponde {"status": "success"}
   UPDATE radiocontrol SET sent_internet = 1 WHERE id = 123
   ```

### **📡 Sistema Keepalive (`callhome.py`)**

Ogni dispositivo invia periodicamente un "heartbeat" al server:

```python
# Ogni 20 secondi (configurabile)
payload = {
    'name': 'reader-01',
    'pkey': 'abc123def456...',
    'action': 'keepalive',
    'timestamp': '2025-01-07T10:30:00Z',
    'system_status': {
        'cpu_percent': 15.2,
        'memory_percent': 45.8,
        'disk_percent': 23.1,
        'uptime_hours': 72.5,
        'temperature': 42.3
    },
    'client_version': '3.1'
}
```

## 🔧 **Configurazione Identità Dispositivo**

### **🚀 Deploy Automatico**

Il sistema `deploy_raspberry.py` genera automaticamente l'identità:

```python
def generate_device_identity(device_type, device_name):
    """Genera identità univoca per il dispositivo"""
    
    # Nome dispositivo (fornito dall'utente)
    name = device_name  # es: "reader-01", "receiver-main"
    
    # Chiave privata univoca (generata automaticamente)
    import secrets, string
    alphabet = string.ascii_letters + string.digits
    pkey = ''.join(secrets.choice(alphabet) for _ in range(48))
    
    return name, pkey

# Inserimento nel database locale
cursor.execute("INSERT INTO costanti VALUES ('nome', %s)", (name,))
cursor.execute("INSERT INTO costanti VALUES ('pkey', %s)", (pkey,))
```

### **🔐 Sicurezza della Chiave Privata**

- **Lunghezza**: 48+ caratteri alfanumerici
- **Entropia**: ~287 bit (estremamente sicura)
- **Generazione**: `secrets` module (crittograficamente sicuro)
- **Unicità**: Probabilità collisione < 1 su 10^86

## 📊 **Database Remoto - Struttura**

### **🗃️ Tabella Punzonature Remote**

```sql
CREATE TABLE punches_remote (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_name VARCHAR(50) NOT NULL,           -- "reader-01"
    device_pkey VARCHAR(100) NOT NULL,          -- chiave privata
    local_id INT NOT NULL,                      -- ID originale dispositivo
    control VARCHAR(10) NOT NULL,               -- numero controllo
    card_number VARCHAR(20) NOT NULL,           -- numero chip
    punch_time DATETIME NOT NULL,               -- timestamp punzonatura
    received_time DATETIME DEFAULT NOW(),       -- timestamp ricezione server
    event_id INT,                               -- ID evento (se applicabile)
    INDEX idx_device (device_name),
    INDEX idx_control (control),
    INDEX idx_card (card_number),
    INDEX idx_punch_time (punch_time),
    UNIQUE KEY unique_punch (device_name, local_id)  -- evita duplicati
);
```

### **🔍 Query Esempio**

```sql
-- Tutte le punzonature di un dispositivo
SELECT * FROM punches_remote 
WHERE device_name = 'reader-01' 
ORDER BY punch_time DESC;

-- Punzonature per controllo specifico
SELECT device_name, card_number, punch_time 
FROM punches_remote 
WHERE control = '31' 
ORDER BY punch_time;

-- Statistiche per evento
SELECT 
    device_name,
    COUNT(*) as total_punches,
    MIN(punch_time) as first_punch,
    MAX(punch_time) as last_punch
FROM punches_remote 
WHERE DATE(punch_time) = '2025-01-07'
GROUP BY device_name;
```

## 🛡️ **Sicurezza e Autenticazione**

### **🔐 Validazione Server-Side**

Il server `receive_data.php` deve validare ogni richiesta:

```php
// Validazione chiave privata
function validateDevice($name, $pkey) {
    // 1. Verifica formato chiave (48+ caratteri alfanumerici)
    if (!preg_match('/^[a-zA-Z0-9]{48,}$/', $pkey)) {
        return false;
    }
    
    // 2. Verifica esistenza dispositivo in database autorizzati
    $stmt = $pdo->prepare("SELECT id FROM authorized_devices WHERE name = ? AND pkey = ?");
    $stmt->execute([$name, $pkey]);
    return $stmt->fetch() !== false;
}

// Processo richiesta
$input = json_decode(file_get_contents('php://input'), true);
$name = $input['name'] ?? '';
$pkey = $input['pkey'] ?? '';

if (!validateDevice($name, $pkey)) {
    http_response_code(401);
    echo json_encode(['status' => 'error', 'message' => 'Unauthorized device']);
    exit;
}

// Processa punzonatura...
```

### **🚨 Registrazione Dispositivi**

I nuovi dispositivi devono essere **autorizzati manualmente**:

```sql
-- Tabella dispositivi autorizzati
CREATE TABLE authorized_devices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    pkey VARCHAR(100) UNIQUE NOT NULL,
    device_type ENUM('reader', 'receiver') NOT NULL,
    created_at DATETIME DEFAULT NOW(),
    last_seen DATETIME,
    active BOOLEAN DEFAULT TRUE
);

-- Registrazione nuovo dispositivo (manuale)
INSERT INTO authorized_devices (name, pkey, device_type) 
VALUES ('reader-01', 'abc123def456...', 'reader');
```

## 🔄 **Flusso Completo**

### **📋 Scenario Tipico:**

1. **Deploy Dispositivo**:
   ```bash
   python3 scripts/deploy_raspberry.py reader reader-01 --auto-start
   ```

2. **Generazione Identità**:
   - Nome: `reader-01`
   - Chiave: `abc123def456ghi789jkl012mno345pqr678stu901vwx234yz`

3. **Registrazione Manuale Server**:
   ```sql
   INSERT INTO authorized_devices VALUES (NULL, 'reader-01', 'abc123def...', 'reader', NOW(), NULL, TRUE);
   ```

4. **Funzionamento Automatico**:
   - Punzonature salvate localmente
   - `send_data_internet.py` invia con identità
   - Server valida e salva
   - `callhome.py` invia keepalive

## 🎯 **Vantaggi del Sistema**

### ✅ **Sicurezza**
- Ogni dispositivo ha identità univoca crittograficamente sicura
- Impossibile falsificare punzonature senza chiave privata
- Validazione server-side di ogni richiesta

### ✅ **Tracciabilità**
- Ogni punzonatura è tracciata al dispositivo di origine
- Log completi di tutti gli invii
- Statistiche per dispositivo e evento

### ✅ **Scalabilità**
- Sistema supporta centinaia di dispositivi
- Database ottimizzato con indici appropriati
- Gestione automatica duplicati

### ✅ **Affidabilità**
- Retry automatici in caso di errori di rete
- Punzonature mai perse (salvate localmente)
- Keepalive per monitoraggio stato dispositivi

---

**🔐 Sistema progettato per garantire integrità e sicurezza dei dati di gara**

*Documentazione tecnica per OriBruni*

-- ============================================================================
-- Script di Inizializzazione Database OriBruni Raspberry RECEIVER
-- ============================================================================
-- Crea tabelle e indici necessari per il sistema Meshtastic
-- ============================================================================

USE OriBruniRadioControls;

-- Tabella per messaggi generici Meshtastic
CREATE TABLE IF NOT EXISTS messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  node_eui VARCHAR(32) NOT NULL,
  field1 VARCHAR(255),
  field2 VARCHAR(255),
  field3 VARCHAR(255),
  raw TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_timestamp (timestamp),
  INDEX idx_node_eui (node_eui),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabella per punzonature orienteering
CREATE TABLE IF NOT EXISTS punches (
  id INT AUTO_INCREMENT PRIMARY KEY,
  timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  name VARCHAR(255),
  pkey VARCHAR(255),
  record_id VARCHAR(255),
  control VARCHAR(255),
  card_number VARCHAR(255),
  punch_time VARCHAR(255),
  raw TEXT,
  processed BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_timestamp (timestamp),
  INDEX idx_record_id (record_id),
  INDEX idx_control (control),
  INDEX idx_card_number (card_number),
  INDEX idx_punch_time (punch_time),
  INDEX idx_processed (processed),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabella per nodi della rete mesh
CREATE TABLE IF NOT EXISTS mesh_nodes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  node_id VARCHAR(32) NOT NULL UNIQUE,
  node_name VARCHAR(255),
  hardware_model VARCHAR(100),
  firmware_version VARCHAR(50),
  battery_level INT,
  voltage FLOAT,
  channel_utilization FLOAT,
  air_util_tx FLOAT,
  last_seen DATETIME,
  latitude DECIMAL(10, 8),
  longitude DECIMAL(11, 8),
  altitude INT,
  is_online BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_node_id (node_id),
  INDEX idx_last_seen (last_seen),
  INDEX idx_is_online (is_online),
  INDEX idx_location (latitude, longitude)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabella per collegamenti tra nodi (topologia rete)
CREATE TABLE IF NOT EXISTS mesh_links (
  id INT AUTO_INCREMENT PRIMARY KEY,
  from_node VARCHAR(32) NOT NULL,
  to_node VARCHAR(32) NOT NULL,
  snr FLOAT,
  rssi INT,
  hop_limit INT,
  want_ack BOOLEAN DEFAULT FALSE,
  last_seen DATETIME,
  packet_count INT DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY unique_link (from_node, to_node),
  INDEX idx_from_node (from_node),
  INDEX idx_to_node (to_node),
  INDEX idx_last_seen (last_seen),
  INDEX idx_snr (snr),
  INDEX idx_rssi (rssi),
  FOREIGN KEY (from_node) REFERENCES mesh_nodes(node_id) ON DELETE CASCADE,
  FOREIGN KEY (to_node) REFERENCES mesh_nodes(node_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabella per eventi di sistema
CREATE TABLE IF NOT EXISTS system_events (
  id INT AUTO_INCREMENT PRIMARY KEY,
  event_type ENUM('INFO', 'WARNING', 'ERROR', 'CRITICAL') NOT NULL,
  source VARCHAR(100) NOT NULL,
  message TEXT NOT NULL,
  details JSON,
  timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  acknowledged BOOLEAN DEFAULT FALSE,
  acknowledged_by VARCHAR(100),
  acknowledged_at DATETIME,
  INDEX idx_event_type (event_type),
  INDEX idx_source (source),
  INDEX idx_timestamp (timestamp),
  INDEX idx_acknowledged (acknowledged)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabella per configurazioni sistema
CREATE TABLE IF NOT EXISTS system_config (
  id INT AUTO_INCREMENT PRIMARY KEY,
  config_key VARCHAR(100) NOT NULL UNIQUE,
  config_value TEXT,
  config_type ENUM('STRING', 'INTEGER', 'FLOAT', 'BOOLEAN', 'JSON') DEFAULT 'STRING',
  description TEXT,
  is_editable BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabella per statistiche sistema
CREATE TABLE IF NOT EXISTS system_stats (
  id INT AUTO_INCREMENT PRIMARY KEY,
  stat_name VARCHAR(100) NOT NULL,
  stat_value DECIMAL(15,4),
  stat_unit VARCHAR(20),
  timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_stat_name (stat_name),
  INDEX idx_timestamp (timestamp),
  INDEX idx_stat_name_timestamp (stat_name, timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Inserimento configurazioni di default
INSERT INTO system_config (config_key, config_value, config_type, description, is_editable) VALUES
('system.version', '1.0.0', 'STRING', 'Versione del sistema OriBruni Receiver', FALSE),
('system.installation_date', NOW(), 'STRING', 'Data di installazione del sistema', FALSE),
('mesh.auto_discovery', 'true', 'BOOLEAN', 'Abilita auto-discovery dispositivi Meshtastic', TRUE),
('mesh.refresh_interval', '5000', 'INTEGER', 'Intervallo aggiornamento rete mesh (ms)', TRUE),
('database.backup_enabled', 'true', 'BOOLEAN', 'Abilita backup automatico database', TRUE),
('database.backup_retention_days', '30', 'INTEGER', 'Giorni di retention backup', TRUE),
('lcd.enabled', 'true', 'BOOLEAN', 'Abilita display LCD', TRUE),
('lcd.update_interval', '30', 'INTEGER', 'Intervallo aggiornamento LCD (secondi)', TRUE),
('lcd.i2c_address', '0x27', 'STRING', 'Indirizzo I2C display LCD', TRUE),
('api.rate_limit', '100', 'INTEGER', 'Rate limit API (richieste/minuto)', TRUE),
('logging.level', 'INFO', 'STRING', 'Livello di logging', TRUE),
('security.session_timeout', '3600', 'INTEGER', 'Timeout sessione (secondi)', TRUE)
ON DUPLICATE KEY UPDATE 
config_value = VALUES(config_value),
updated_at = CURRENT_TIMESTAMP;

-- Inserimento evento di inizializzazione
INSERT INTO system_events (event_type, source, message, details) VALUES
('INFO', 'DATABASE', 'Database inizializzato correttamente', JSON_OBJECT('version', '1.0.0', 'timestamp', NOW()));

-- Creazione viste utili
CREATE OR REPLACE VIEW v_active_nodes AS
SELECT 
    n.*,
    TIMESTAMPDIFF(MINUTE, n.last_seen, NOW()) as minutes_since_last_seen
FROM mesh_nodes n 
WHERE n.is_online = TRUE 
ORDER BY n.last_seen DESC;

CREATE OR REPLACE VIEW v_recent_punches AS
SELECT 
    p.*,
    TIMESTAMPDIFF(MINUTE, p.timestamp, NOW()) as minutes_ago
FROM punches p 
WHERE p.timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY p.timestamp DESC;

CREATE OR REPLACE VIEW v_mesh_topology AS
SELECT 
    ml.from_node,
    fn.node_name as from_name,
    ml.to_node,
    tn.node_name as to_name,
    ml.snr,
    ml.rssi,
    ml.last_seen,
    TIMESTAMPDIFF(MINUTE, ml.last_seen, NOW()) as minutes_since_last_seen
FROM mesh_links ml
LEFT JOIN mesh_nodes fn ON ml.from_node = fn.node_id
LEFT JOIN mesh_nodes tn ON ml.to_node = tn.node_id
WHERE ml.last_seen >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
ORDER BY ml.last_seen DESC;

-- Stored procedure per pulizia dati vecchi
DELIMITER //
CREATE PROCEDURE CleanOldData()
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    
    START TRANSACTION;
    
    -- Rimuovi messaggi più vecchi di 7 giorni
    DELETE FROM messages WHERE timestamp < DATE_SUB(NOW(), INTERVAL 7 DAY);
    
    -- Rimuovi eventi di sistema più vecchi di 30 giorni
    DELETE FROM system_events WHERE timestamp < DATE_SUB(NOW(), INTERVAL 30 DAY);
    
    -- Rimuovi statistiche più vecchie di 90 giorni
    DELETE FROM system_stats WHERE timestamp < DATE_SUB(NOW(), INTERVAL 90 DAY);
    
    -- Rimuovi link mesh non visti da più di 24 ore
    DELETE FROM mesh_links WHERE last_seen < DATE_SUB(NOW(), INTERVAL 24 HOUR);
    
    -- Marca nodi offline se non visti da più di 1 ora
    UPDATE mesh_nodes SET is_online = FALSE 
    WHERE last_seen < DATE_SUB(NOW(), INTERVAL 1 HOUR) AND is_online = TRUE;
    
    COMMIT;
    
    -- Log dell'operazione
    INSERT INTO system_events (event_type, source, message) 
    VALUES ('INFO', 'MAINTENANCE', 'Pulizia dati vecchi completata');
    
END //
DELIMITER ;

-- Event scheduler per pulizia automatica (esegue ogni giorno alle 02:00)
SET GLOBAL event_scheduler = ON;

CREATE EVENT IF NOT EXISTS daily_cleanup
ON SCHEDULE EVERY 1 DAY
STARTS TIMESTAMP(CURDATE() + INTERVAL 1 DAY, '02:00:00')
DO
  CALL CleanOldData();

-- Trigger per aggiornamento automatico timestamp
DELIMITER //
CREATE TRIGGER tr_messages_updated 
    BEFORE UPDATE ON messages
    FOR EACH ROW 
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END //

CREATE TRIGGER tr_punches_updated 
    BEFORE UPDATE ON punches
    FOR EACH ROW 
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END //

CREATE TRIGGER tr_mesh_nodes_updated 
    BEFORE UPDATE ON mesh_nodes
    FOR EACH ROW 
BEGIN
    SET NEW.updated_at = CURRENT_TIMESTAMP;
END //
DELIMITER ;

-- Inserimento dati di test (opzionale)
-- INSERT INTO mesh_nodes (node_id, node_name, hardware_model, is_online, last_seen) VALUES
-- ('!12345678', 'Base Station', 'HELTEC_V3', TRUE, NOW()),
-- ('!87654321', 'Mobile Unit 1', 'TBEAM', TRUE, DATE_SUB(NOW(), INTERVAL 5 MINUTE));

-- Commit finale
COMMIT;

-- Log completamento inizializzazione
INSERT INTO system_events (event_type, source, message, details) VALUES
('INFO', 'DATABASE', 'Inizializzazione database completata', 
JSON_OBJECT(
    'tables_created', 7,
    'views_created', 3,
    'procedures_created', 1,
    'events_created', 1,
    'triggers_created', 3
));

-- Mostra riepilogo
SELECT 'Database OriBruni Receiver inizializzato correttamente' as status;
SELECT COUNT(*) as total_tables FROM information_schema.tables WHERE table_schema = 'OriBruniRadioControls';
SELECT COUNT(*) as total_views FROM information_schema.views WHERE table_schema = 'OriBruniRadioControls';

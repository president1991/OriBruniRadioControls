# ============================================================================
# Makefile per OriBruni Raspberry RECEIVER
# ============================================================================
# Comandi semplificati per gestione Docker
# Utilizzo: make <comando>
# ============================================================================

.PHONY: help build up down restart logs status clean backup restore

# Configurazione
COMPOSE_FILE = docker-compose.yml
PROJECT_NAME = oribruni-receiver

# Colori per output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m

# Help - mostra comandi disponibili
help:
	@echo "$(GREEN)OriBruni Raspberry RECEIVER - Comandi Docker$(NC)"
	@echo ""
	@echo "$(YELLOW)Comandi principali:$(NC)"
	@echo "  make up          - Avvia tutti i servizi"
	@echo "  make down        - Ferma tutti i servizi"
	@echo "  make restart     - Riavvia tutti i servizi"
	@echo "  make status      - Mostra stato servizi"
	@echo "  make logs        - Mostra logs in tempo reale"
	@echo ""
	@echo "$(YELLOW)Build e sviluppo:$(NC)"
	@echo "  make build       - Build immagini Docker"
	@echo "  make rebuild     - Rebuild forzato immagini"
	@echo "  make update      - Aggiorna e riavvia servizi"
	@echo ""
	@echo "$(YELLOW)Servizi specifici:$(NC)"
	@echo "  make up-core     - Avvia solo servizi essenziali"
	@echo "  make up-full     - Avvia tutti i servizi incluso LCD"
	@echo "  make up-dev      - Avvia in modalità sviluppo"
	@echo ""
	@echo "$(YELLOW)Database:$(NC)"
	@echo "  make db-shell    - Accesso shell MySQL"
	@echo "  make db-backup   - Backup database"
	@echo "  make db-restore  - Restore database (richiede BACKUP_FILE)"
	@echo ""
	@echo "$(YELLOW)Manutenzione:$(NC)"
	@echo "  make clean       - Pulizia sistema Docker"
	@echo "  make clean-all   - Pulizia completa (ATTENZIONE: rimuove volumi)"
	@echo "  make health      - Verifica salute servizi"
	@echo ""
	@echo "$(YELLOW)Debug:$(NC)"
	@echo "  make shell       - Shell container applicazione"
	@echo "  make logs-app    - Logs solo applicazione"
	@echo "  make logs-db     - Logs solo database"
	@echo "  make logs-nginx  - Logs solo nginx"

# Comandi principali
up:
	@echo "$(GREEN)Avvio servizi OriBruni Receiver...$(NC)"
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "$(GREEN)Servizi avviati. Accesso web: http://localhost$(NC)"

down:
	@echo "$(YELLOW)Arresto servizi...$(NC)"
	docker compose -f $(COMPOSE_FILE) down

restart:
	@echo "$(YELLOW)Riavvio servizi...$(NC)"
	docker compose -f $(COMPOSE_FILE) restart

status:
	@echo "$(GREEN)Stato servizi:$(NC)"
	docker compose -f $(COMPOSE_FILE) ps

logs:
	@echo "$(GREEN)Logs in tempo reale (Ctrl+C per uscire):$(NC)"
	docker compose -f $(COMPOSE_FILE) logs -f

# Build e sviluppo
build:
	@echo "$(GREEN)Build immagini Docker...$(NC)"
	docker compose -f $(COMPOSE_FILE) build

rebuild:
	@echo "$(GREEN)Rebuild forzato immagini...$(NC)"
	docker compose -f $(COMPOSE_FILE) build --no-cache

update:
	@echo "$(GREEN)Aggiornamento sistema...$(NC)"
	docker compose -f $(COMPOSE_FILE) pull
	docker compose -f $(COMPOSE_FILE) up -d --build
	@echo "$(GREEN)Sistema aggiornato$(NC)"

# Servizi specifici
up-core:
	@echo "$(GREEN)Avvio servizi essenziali...$(NC)"
	docker compose -f $(COMPOSE_FILE) up -d mysql app nginx

up-full:
	@echo "$(GREEN)Avvio servizi completi...$(NC)"
	docker compose -f $(COMPOSE_FILE) up -d mysql app nginx phpmyadmin lcd-display

up-dev:
	@echo "$(GREEN)Avvio modalità sviluppo...$(NC)"
	docker compose -f $(COMPOSE_FILE) up mysql app nginx phpmyadmin

# Database
db-shell:
	@echo "$(GREEN)Accesso shell MySQL...$(NC)"
	docker compose -f $(COMPOSE_FILE) exec mysql mysql -u root -pPuhA7gWCrW OriBruniRadioControls

db-backup:
	@echo "$(GREEN)Backup database...$(NC)"
	docker compose -f $(COMPOSE_FILE) --profile backup run --rm backup

db-restore:
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "$(RED)Errore: specificare BACKUP_FILE=path/to/backup.sql.gz$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Restore database da $(BACKUP_FILE)...$(NC)"
	@echo "$(RED)ATTENZIONE: Questo sovrascriverà il database esistente!$(NC)"
	@read -p "Continuare? (y/N): " confirm && [ "$$confirm" = "y" ]
	docker compose -f $(COMPOSE_FILE) stop app
	gunzip -c $(BACKUP_FILE) | docker compose -f $(COMPOSE_FILE) exec -T mysql mysql -u root -pPuhA7gWCrW OriBruniRadioControls
	docker compose -f $(COMPOSE_FILE) start app
	@echo "$(GREEN)Restore completato$(NC)"

# Manutenzione
clean:
	@echo "$(YELLOW)Pulizia sistema Docker...$(NC)"
	docker container prune -f
	docker image prune -f
	docker network prune -f
	@echo "$(GREEN)Pulizia completata$(NC)"

clean-all:
	@echo "$(RED)ATTENZIONE: Questa operazione rimuoverà TUTTI i dati!$(NC)"
	@read -p "Continuare? (y/N): " confirm && [ "$$confirm" = "y" ]
	docker compose -f $(COMPOSE_FILE) down -v
	docker system prune -af --volumes
	@echo "$(GREEN)Pulizia completa eseguita$(NC)"

health:
	@echo "$(GREEN)Verifica salute servizi:$(NC)"
	@echo ""
	@echo "$(YELLOW)Container status:$(NC)"
	docker compose -f $(COMPOSE_FILE) ps
	@echo ""
	@echo "$(YELLOW)Health checks:$(NC)"
	@docker compose -f $(COMPOSE_FILE) exec app curl -f http://localhost:5000/health 2>/dev/null && echo "✓ App: OK" || echo "✗ App: FAIL"
	@docker compose -f $(COMPOSE_FILE) exec mysql mysqladmin ping -u root -pPuhA7gWCrW --silent 2>/dev/null && echo "✓ MySQL: OK" || echo "✗ MySQL: FAIL"
	@curl -f http://localhost:80 >/dev/null 2>&1 && echo "✓ Nginx: OK" || echo "✗ Nginx: FAIL"
	@echo ""
	@echo "$(YELLOW)Utilizzo risorse:$(NC)"
	docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Debug
shell:
	@echo "$(GREEN)Shell container applicazione...$(NC)"
	docker compose -f $(COMPOSE_FILE) exec app bash

shell-root:
	@echo "$(GREEN)Shell root container applicazione...$(NC)"
	docker compose -f $(COMPOSE_FILE) exec --user root app bash

logs-app:
	@echo "$(GREEN)Logs applicazione:$(NC)"
	docker compose -f $(COMPOSE_FILE) logs -f app

logs-db:
	@echo "$(GREEN)Logs database:$(NC)"
	docker compose -f $(COMPOSE_FILE) logs -f mysql

logs-nginx:
	@echo "$(GREEN)Logs nginx:$(NC)"
	docker compose -f $(COMPOSE_FILE) logs -f nginx

logs-lcd:
	@echo "$(GREEN)Logs LCD display:$(NC)"
	docker compose -f $(COMPOSE_FILE) logs -f lcd-display

# Comandi di utilità
config:
	@echo "$(GREEN)Verifica configurazione Docker Compose:$(NC)"
	docker compose -f $(COMPOSE_FILE) config

ps:
	@echo "$(GREEN)Processi Docker:$(NC)"
	docker compose -f $(COMPOSE_FILE) ps -a

top:
	@echo "$(GREEN)Processi nei container:$(NC)"
	docker compose -f $(COMPOSE_FILE) top

stats:
	@echo "$(GREEN)Statistiche utilizzo risorse:$(NC)"
	docker stats

# Installazione e setup
install-docker:
	@echo "$(GREEN)Installazione Docker...$(NC)"
	curl -fsSL https://get.docker.com -o get-docker.sh
	sudo sh get-docker.sh
	sudo usermod -aG docker $$USER
	sudo apt install -y docker-compose-plugin
	@echo "$(YELLOW)Riavvia il sistema per completare l'installazione$(NC)"

setup:
	@echo "$(GREEN)Setup iniziale progetto...$(NC)"
	mkdir -p data/mysql logs/nginx backups nginx/ssl
	chmod +x scripts/backup.sh
	sudo chown -R $$USER:$$USER .
	chmod 755 data logs backups
	@echo "$(GREEN)Setup completato$(NC)"

# Test e validazione
test:
	@echo "$(GREEN)Test sistema...$(NC)"
	@echo "$(YELLOW)Test connessione database:$(NC)"
	@docker compose -f $(COMPOSE_FILE) exec app python -c "import mysql.connector; print('✓ MySQL connector OK')" 2>/dev/null || echo "✗ MySQL connector FAIL"
	@echo "$(YELLOW)Test connessione Meshtastic:$(NC)"
	@docker compose -f $(COMPOSE_FILE) exec app python -c "import meshtastic; print('✓ Meshtastic library OK')" 2>/dev/null || echo "✗ Meshtastic library FAIL"
	@echo "$(YELLOW)Test Flask:$(NC)"
	@docker compose -f $(COMPOSE_FILE) exec app python -c "import flask; print('✓ Flask OK')" 2>/dev/null || echo "✗ Flask FAIL"

# Informazioni sistema
info:
	@echo "$(GREEN)Informazioni sistema:$(NC)"
	@echo "$(YELLOW)Docker version:$(NC)"
	docker --version
	@echo "$(YELLOW)Docker Compose version:$(NC)"
	docker compose version
	@echo "$(YELLOW)Sistema operativo:$(NC)"
	uname -a
	@echo "$(YELLOW)Spazio disco:$(NC)"
	df -h
	@echo "$(YELLOW)Memoria:$(NC)"
	free -h

# Default target
.DEFAULT_GOAL := help

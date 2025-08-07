#!/bin/bash
# Quick Setup OriBruni RadioControls
# Script di installazione rapida per nuovi dispositivi

set -e

# Colori per output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🏃‍♂️ OriBruni RadioControls - Quick Setup${NC}"
echo -e "${BLUE}============================================${NC}"
echo

# Verifica se siamo su Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo -e "${YELLOW}⚠️  ATTENZIONE: Non sembra essere un Raspberry Pi${NC}"
    read -p "Continuare comunque? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ Setup annullato${NC}"
        exit 1
    fi
fi

# Verifica permessi (non deve essere root)
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}❌ ERRORE: Non eseguire come root. Usa l'utente 'pi'.${NC}"
    exit 1
fi

# Verifica connessione internet
echo -e "${BLUE}🌐 Verifica connessione internet...${NC}"
if ! ping -c 1 google.com &> /dev/null; then
    echo -e "${RED}❌ Nessuna connessione internet disponibile${NC}"
    echo "   Verifica la connessione WiFi/Ethernet e riprova"
    exit 1
fi
echo -e "${GREEN}✅ Connessione internet OK${NC}"

# Aggiorna sistema se necessario
echo -e "${BLUE}📦 Aggiornamento sistema...${NC}"
sudo apt-get update -qq

# Installa Python3 e pip se non presenti
if ! command -v python3 &> /dev/null; then
    echo -e "${BLUE}🐍 Installazione Python3...${NC}"
    sudo apt-get install -y python3 python3-pip
fi

# Installa requests per lo script di installazione
echo -e "${BLUE}📚 Installazione dipendenze base...${NC}"
pip3 install --user requests configparser

echo
echo -e "${GREEN}✅ Sistema preparato!${NC}"
echo

# Chiedi tipo di dispositivo
echo -e "${BLUE}📱 Che tipo di dispositivo vuoi configurare?${NC}"
echo "1) 🔴 LETTORE (RadioControl) - Legge punzonature SportIdent"
echo "2) 🔵 RICEVITORE (Receiver) - Raccoglie dati e gestisce database"
echo
read -p "Scegli (1 o 2): " -n 1 -r device_choice
echo

case $device_choice in
    1)
        DEVICE_TYPE="reader"
        echo -e "${GREEN}✅ Configurazione LETTORE selezionata${NC}"
        ;;
    2)
        DEVICE_TYPE="receiver"
        echo -e "${GREEN}✅ Configurazione RICEVITORE selezionata${NC}"
        ;;
    *)
        echo -e "${RED}❌ Scelta non valida${NC}"
        exit 1
        ;;
esac

echo

# Installazione dispositivo con verifica online
echo -e "${BLUE}🔧 Installazione e configurazione dispositivo...${NC}"
echo -e "${YELLOW}📝 Ti verranno chiesti nome dispositivo e chiave (pkey)${NC}"
echo

if python3 install_device.py; then
    echo -e "${GREEN}✅ Dispositivo configurato con successo!${NC}"
else
    echo -e "${RED}❌ Errore durante la configurazione del dispositivo${NC}"
    echo "   Controlla i log in logs/install.log"
    exit 1
fi

# Leggi il nome del dispositivo dalla configurazione
if [ -f "config/config.ini" ]; then
    DEVICE_NAME=$(python3 -c "
import configparser
config = configparser.ConfigParser()
config.read('config/config.ini')
if config.has_section('DEVICE'):
    print(config.get('DEVICE', 'name', fallback='unknown'))
else:
    print('unknown')
" 2>/dev/null || echo "unknown")
else
    DEVICE_NAME="unknown"
fi

if [ "$DEVICE_NAME" = "unknown" ]; then
    echo -e "${YELLOW}⚠️  Impossibile leggere il nome del dispositivo${NC}"
    read -p "Inserisci il nome del dispositivo: " DEVICE_NAME
fi

echo
echo -e "${BLUE}🚀 Deploy automatico del sistema...${NC}"
echo -e "${YELLOW}📝 Questo processo può richiedere alcuni minuti${NC}"
echo

# Deploy automatico
if python3 scripts/deploy_raspberry.py "$DEVICE_TYPE" "$DEVICE_NAME" --auto-start; then
    echo
    echo -e "${GREEN}🎉 SETUP COMPLETATO CON SUCCESSO!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo
    echo -e "${GREEN}✅ Dispositivo '$DEVICE_NAME' configurato come $DEVICE_TYPE${NC}"
    echo -e "${GREEN}✅ Servizi installati e avviati automaticamente${NC}"
    echo -e "${GREEN}✅ Sistema pronto per l'uso${NC}"
    echo
    echo -e "${BLUE}📊 MONITORAGGIO:${NC}"
    echo "   - Stato servizi: systemctl status oribruni-*"
    echo "   - Log in tempo reale: journalctl -f -u oribruni-*"
    echo "   - Health check: ./health_check.sh"
    echo
    echo -e "${BLUE}🔧 GESTIONE:${NC}"
    echo "   - Avvio: ./start_oribruni.sh"
    echo "   - Test API: python3 test_api_connection.py"
    echo "   - Backup: ./backup.sh"
    echo
    if [ "$DEVICE_TYPE" = "receiver" ]; then
        echo -e "${BLUE}🌐 DASHBOARD WEB:${NC}"
        echo "   - URL: http://$(hostname -I | awk '{print $1}'):8000"
        echo "   - API: http://$(hostname -I | awk '{print $1}'):8000/api/status"
        echo
    fi
    echo -e "${BLUE}📚 DOCUMENTAZIONE:${NC}"
    echo "   - docs/INSTALLAZIONE_DISPOSITIVO.md"
    echo "   - docs/GUIDA_RAPIDA_INSTALLAZIONE.md"
    echo
    echo -e "${GREEN}🏃‍♂️ Buona fortuna con il tuo evento di orienteering! 🧭${NC}"
    
else
    echo
    echo -e "${RED}❌ ERRORE durante il deploy automatico${NC}"
    echo "   Il dispositivo è configurato ma i servizi potrebbero non essere attivi"
    echo "   Controlla i log in logs/deploy.log"
    echo
    echo -e "${YELLOW}🔧 PROSSIMI PASSI MANUALI:${NC}"
    echo "   1. Verifica configurazione hardware"
    echo "   2. Esegui: python3 scripts/deploy_raspberry.py $DEVICE_TYPE $DEVICE_NAME"
    echo "   3. Avvia servizi: ./start_oribruni.sh"
    exit 1
fi

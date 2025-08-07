#!/bin/bash

# Questo script installa il servizio systemd per Simple Meshtastic Listener.
# Deve essere eseguito con privilegi di root (sudo).

set -e

echo "Installazione del servizio Simple Meshtastic Listener..."

# Copia il file di servizio nella directory di systemd
echo "Copia del file di servizio..."
cp simple-meshtastic-listener.service /etc/systemd/system/

# Ricarica il demone di systemd per riconoscere il nuovo servizio
echo "Ricaricamento del demone di systemd..."
systemctl daemon-reload

# Abilita il servizio per l'avvio automatico al boot
echo "Abilitazione del servizio..."
systemctl enable simple-meshtastic-listener.service

echo "Servizio Simple Meshtastic Listener installato e abilitato con successo."
echo "Puoi avviare il servizio con:"
echo "sudo systemctl start simple-meshtastic-listener.service"

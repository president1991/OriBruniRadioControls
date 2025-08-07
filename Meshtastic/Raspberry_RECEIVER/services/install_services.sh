#!/bin/bash

# Questo script installa i servizi systemd per il progetto OriBruni Raspberry RECEIVER.
# Deve essere eseguito con privilegi di root (sudo).

set -e

echo "Installazione dei servizi systemd..."

# Copia i file di servizio nella directory di systemd
echo "Copia dei file di servizio..."
cp meshtastic-interface.service /etc/systemd/system/
cp flask-server.service /etc/systemd/system/
cp lcd-display.service /etc/systemd/system/

# Ricarica il demone di systemd per riconoscere i nuovi servizi
echo "Ricaricamento del demone di systemd..."
systemctl daemon-reload

# Abilita i servizi per l'avvio automatico al boot
echo "Abilitazione dei servizi..."
systemctl enable flask-server.service
systemctl enable lcd-display.service

echo "Servizi installati e abilitati con successo."
echo "Puoi avviare i servizi con:"
echo "sudo systemctl start flask-server.service"
echo "sudo systemctl start lcd-display.service"

#!/bin/bash

# Script per la rimozione completa di Docker e di tutti i suoi dati
# dal Raspberry Pi. Eseguire con cautela!

set -e

echo "================================================="
echo "Inizio rimozione completa di Docker"
echo "================================================="

# 1. Stop di tutti i container in esecuzione
echo "--> 1/5: Stop di tutti i container Docker..."
docker stop $(docker ps -aq)

# 2. Rimozione di tutti i container
echo "--> 2/5: Rimozione di tutti i container Docker..."
docker rm $(docker ps -aq)

# 3. Rimozione di tutte le immagini Docker
echo "--> 3/5: Rimozione di tutte le immagini Docker..."
docker rmi $(docker images -q)

# 4. Rimozione di tutti i volumi Docker
echo "--> 4/5: Rimozione di tutti i volumi Docker..."
docker volume rm $(docker volume ls -q)

# 5. Disinstallazione di Docker
echo "--> 5/5: Disinstallazione di Docker Engine, CLI e Containerd..."
sudo apt-get purge -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo apt-get autoremove -y --purge
sudo rm -rf /var/lib/docker
sudo rm -rf /var/lib/containerd

echo "================================================="
echo "Rimozione di Docker completata!"
echo "================================================="

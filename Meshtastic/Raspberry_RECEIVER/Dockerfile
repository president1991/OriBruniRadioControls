# ============================================================================
# Dockerfile per OriBruni Raspberry RECEIVER
# ============================================================================
# Multi-stage build per ottimizzare dimensioni immagine
# Supporta architettura ARM64 per Raspberry Pi 4
# ============================================================================

FROM python:3.11-slim-bullseye as base

# Metadata
LABEL maintainer="OriBruni <support@oribruni.com>"
LABEL description="OriBruni Raspberry RECEIVER - Sistema Meshtastic per orienteering"
LABEL version="1.0.0"

# Variabili di ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libmariadb-dev \
    i2c-tools \
    python3-smbus \
    git \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Crea utente non-root
RUN groupadd -r oribruni && useradd -r -g oribruni oribruni

# Crea directory applicazione
WORKDIR /app

# Copia requirements e installa dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia codice applicazione
COPY . .

# Imposta permessi
RUN chown -R oribruni:oribruni /app

# Espone porte
EXPOSE 5000

# Cambia utente
USER oribruni

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Comando di avvio
CMD ["python", "server.py"]

# ============================================================================
# Dockerfile per OriBruni Raspberry RECEIVER (Multi-Stage)
# ============================================================================
# Stage 1: Builder
# Compila le dipendenze Python in wheels
# ============================================================================
FROM python:3.11-bullseye as builder
# Using full bullseye for the builder stage as it's more likely to have necessary build tools

LABEL stage="builder"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libmariadb-dev \
    # Add other specific build-time system deps if pip install fails later
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements.txt to leverage Docker cache for this layer
COPY requirements.txt .

# Upgrade pip and install wheel package (needed to build wheels)
RUN pip install --no-cache-dir --upgrade pip wheel

# Build wheels for all dependencies. This is the slow part.
# Wheels will be stored in /app/wheels
RUN pip wheel --no-cache-dir -r requirements.txt -w /app/wheels

# ============================================================================
# Stage 2: Final image
# Utilizza i wheels pre-compilati e codice applicazione
# ============================================================================
FROM python:3.11-slim-bullseye as final

LABEL stage="final"
LABEL maintainer="OriBruni <support@oribruni.com>"
LABEL description="OriBruni Raspberry RECEIVER - Sistema Meshtastic per orienteering"
# Consider updating version for new build strategy
LABEL version="1.0.1"

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# Install only essential runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    i2c-tools \
    python3-smbus \
    # libmariadbclient-dev might be needed if mysql-connector-python relies on it at runtime
    # For now, assuming wheels are self-contained or pure Python part works.
    && rm -rf /var/lib/apt/lists/*

# Crea utente non-root
RUN groupadd -r oribruni && useradd --no-log-init -r -g oribruni oribruni

WORKDIR /app

# Copy pre-built wheels from the builder stage
COPY --from=builder /app/wheels /wheels

# Copy requirements.txt again for pip to know what to install from the wheels
COPY requirements.txt .

# Install Python packages from local wheels.
# --no-index ensures pip only uses local wheels from --find-links.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

# Copy application code
# IMPORTANT: Ensure your .dockerignore file is set up correctly to exclude
# .git, venv, __pycache__, local wheels, build artifacts, etc.
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

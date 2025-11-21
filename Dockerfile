# Multi-stage build pour optimiser la taille de l'image
FROM python:3.11-slim as builder

# Variables d'environnement pour Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copier uniquement requirements.txt pour profiter du cache Docker
COPY requirements.txt .

# Installer les dépendances
RUN pip install --user --no-warn-script-location -r requirements.txt

# Stage final - image minimale
FROM python:3.11-slim

# Métadonnées
LABEL maintainer="ClaraVnk"
LABEL description="OpenStack Instance Guardian - Automatic failover monitoring"
LABEL version="2.0.0"

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:$PATH

# Créer un utilisateur non-root pour la sécurité
RUN useradd -m -u 1000 guardian && \
    mkdir -p /app /logs && \
    chown -R guardian:guardian /app /logs

WORKDIR /app

# Copier les dépendances depuis le builder
COPY --from=builder --chown=guardian:guardian /root/.local /home/guardian/.local

# Copier le code de l'application
COPY --chown=guardian:guardian openstack-instance-guardian.py .

# Passer à l'utilisateur non-root
USER guardian

# Volume pour les logs
VOLUME ["/logs"]

# Healthcheck pour vérifier que le script tourne
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "openstack-instance-guardian.py" || exit 1

# Lancer l'application
CMD ["python", "openstack-instance-guardian.py"]

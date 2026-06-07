# ── Étape 1 : image de base Python 3.11 légère ──────────────────────────────
FROM python:3.11-slim
 
# Métadonnées
LABEL maintainer="Minouverse"
LABEL description="API Flask – backend Minouverse"
 
# Empêche Python de créer des fichiers .pyc et tamponne stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
 
# Répertoire de travail dans le conteneur
WORKDIR /app
 
# Dépendances système nécessaires pour psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
 
# Copie et installation des dépendances Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
 
# Copie du code source
COPY . .
 
# Expose le port Flask
EXPOSE 5000
 
# Commande de démarrage
CMD ["python", "app.py"]
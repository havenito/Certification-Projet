# 🐱 Minouverse – Plateforme sociale de partage de contenu
 
> Plateforme sociale inspirée de Twitter/X permettant de publier des « Miaous »,
> suivre des créateurs, échanger en messagerie privée et souscrire à des abonnements premium.
> Projet de certification CDA – École Hexagone – Session Juillet 2026
 
---
 
## 📋 Prérequis
 
Avant de lancer le projet, assurez-vous d'avoir installé :
 
- [Python 3.11+](https://www.python.org/downloads/)
- [Node.js 20+](https://nodejs.org/)
- [Docker & Docker Compose](https://www.docker.com/) *(optionnel mais recommandé)*
- Un compte [Supabase](https://supabase.com/) *(base de données PostgreSQL managée)*
- Un compte [Cloudinary](https://cloudinary.com/) *(hébergement médias)*
- Un compte [Stripe](https://stripe.com/) *(paiements – optionnel)*
---
 
## 📁 Structure du projet
 
```
Twitter_Like/
├── Flask/                      # API REST Backend + WebSocket
│   ├── models/                 # Modèles SQLAlchemy (User, Post, Comment…)
│   ├── routes/                 # Blueprints Flask (auth, posts, chat, admin…)
│   ├── services/               # Upload Cloudinary
│   ├── tests/                  # Tests unitaires et d'intégration (pytest)
│   ├── app.py                  # Point d'entrée Flask + SocketIO
│   ├── config.py               # Configuration (DB, JWT, Mail, Cloudinary)
│   ├── requirements.txt        # Dépendances Python
│   ├── Dockerfile              # Image Python 3.11-slim
│   └── .dockerignore
├── Nextjs/                     # Frontend Next.js 15 (App Router)
│   ├── src/
│   │   ├── app/                # Pages et routes (App Router + route groups)
│   │   ├── components/         # Composants React organisés par domaine
│   │   └── hooks/              # Hooks personnalisés (useSocket, useCreatePost…)
│   ├── public/                 # Assets statiques (logo, favicon, badges)
│   ├── package.json
│   ├── Dockerfile              # Image Node 20-alpine (multi-stage build)
│   └── .dockerignore
├── docker-compose.yml          # Orchestration des deux services
├── docker-compose.dev.yml      # Override hot reload développement
└── README.md
```
 
---
 
## 🚀 Installation et lancement
 
### ▶️ Option 1 – Avec Docker (recommandé)
 
Une seule commande suffit à lancer l'intégralité de l'application.
 
```bash
# 1. Cloner le projet
git clone https://github.com/havenito/Twitter_Like
cd Twitter_Like
 
# 2. Créer les fichiers de variables d'environnement (voir section dédiée)
#    Flask/.flaskenv
#    Nextjs/.env.local
 
# 3. Lancer les conteneurs
docker-compose up --build
```
 
✅ Frontend disponible sur **http://localhost:3000**
✅ Backend disponible sur **http://localhost:5000**
✅ Health check : **http://localhost:5000/api/health**
 
```bash
# Arrêter les conteneurs
docker-compose down
 
# Mode développement avec hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build
 
# Consulter les logs en temps réel
docker-compose logs -f backend
docker-compose logs -f frontend
```
 
---
 
### ▶️ Option 2 – Sans Docker (manuel)
 
**Backend Flask**
 
```bash
cd Flask
pip install -r requirements.txt
python app.py
```
 
✅ API disponible sur **http://localhost:5000**
 
**Frontend Next.js**
 
```bash
cd Nextjs
npm install
npm run dev
```
 
✅ Application disponible sur **http://localhost:3000**
 
---
 
## 🔑 Variables d'environnement
 
Créez les deux fichiers suivants **avant** de lancer l'application.
Ne versionnez jamais ces fichiers — ils sont exclus via `.gitignore`.
 
### 📁 `Flask/.flaskenv`
 
```env
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=1
 
# Base de données Supabase (PostgreSQL managé)
DATABASE_URL=postgresql://user:password@host:5432/postgres
 
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
 
# Cloudinary (hébergement et optimisation des médias)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
 
# Sécurité
SECRET_KEY=your_flask_secret_key
JWT_SECRET_KEY=your_jwt_secret_key
 
# Emails (réinitialisation mot de passe)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_gmail_app_password
MAIL_DEFAULT_SENDER="Minouverse <noreply@minouverse.com>"
 
# Stripe (paiements et abonnements)
STRIPE_SECRET_KEY=sk_test_your_stripe_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
 
# URLs
FRONTEND_URL=http://localhost:3000
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```
 
### 📁 `Nextjs/.env.local`
 
```env
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your_nextauth_secret
 
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
 
# OAuth – Google
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
 
# OAuth – GitHub
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
 
# Stripe
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_key
 
# API Flask
NEXT_PUBLIC_FLASK_API_URL=http://localhost:5000
NEXT_PUBLIC_API_URL=http://localhost:5000
FLASK_API_URL=http://localhost:5000
NEXT_PUBLIC_WEBSOCKET_URL=http://localhost:5000
```
 
---
 
## 💳 Configuration Stripe et Ngrok (optionnel)
 
Pour tester les paiements en local, Stripe a besoin d'une URL publique
pour envoyer ses webhooks.
 
```bash
# 1. Télécharger ngrok : https://ngrok.com/download
 
# 2. Exposer le backend Flask
ngrok http 5000
 
# 3. Copier l'URL HTTPS fournie par ngrok
#    Exemple : https://abc123.ngrok.io
 
# 4. L'ajouter dans le dashboard Stripe
#    Stripe Dashboard > Developers > Webhooks > Add endpoint
#    URL : https://abc123.ngrok.io/api/webhook
 
# 5. Mettre à jour STRIPE_WEBHOOK_SECRET dans Flask/.flaskenv
#    avec le signing secret fourni par Stripe
```
 
**Carte de test Stripe :**
 
| Champ   | Valeur               |
|---------|----------------------|
| Numéro  | 4242 4242 4242 4242  |
| Expiry  | 12/34                |
| CVC     | 123                  |
 
---
 
## 🧪 Lancer les tests
 
```bash
cd Flask
 
# Lancer tous les tests
python -m pytest tests/ -v
 
# Tests unitaires uniquement
python -m pytest tests/test_unit_*.py -v
 
# Tests d'intégration uniquement
python -m pytest tests/test_integration_*.py -v
 
# Avec rapport de couverture de code
python -m pytest tests/ -v --cov=. --cov-report=term
```
 
---
 
## 👤 Comptes de test
 
> ⚠️ Ces comptes doivent être créés via l'interface d'inscription
> ou directement dans la console Supabase avant utilisation.
 
| Rôle          | Email                    | Mot de passe  |
|---------------|--------------------------|---------------|
| Utilisateur   | test@minouverse.com      | Test1234!     |
| Administrateur| admin@minouverse.com     | Admin1234!    |
 
---
 
## ✨ Fonctionnalités principales

- 🔐 **Authentification** – Inscription manuelle + OAuth Google & GitHub (NextAuth)
- 📝 **Publications (Miaous)** – Texte, images, vidéos, GIFs via Cloudinary
- 💬 **Messagerie temps réel** – Chat privé 1-to-1 via Socket.IO
- 👥 **Système social** – Follows, likes, commentaires, réponses imbriquées, favoris
- 📊 **Sondages** – Création et vote avec résultats en temps réel
- 💎 **Abonnements premium** – Free / Plus (4,99€/mois) / Premium (9,99€/mois) via Stripe
- 🔔 **Notifications** – Temps réel pour likes, commentaires, follows, messages et mentions
- 🔍 **Recherche** – Utilisateurs et catégories
- 🏆 **Classement** – Publications et créateurs les plus populaires
- 🛡️ **Panel admin** – Modération, signalements, avertissements, bannissements
- 📱 **Responsive** – Design mobile-first avec Tailwind CSS
- @ **Mentions** – Autocomplétion @pseudo lors de la rédaction avec notification automatique
- 🐳 **Docker** – Environnement conteneurisé, lancement en une commande
---
 
## 📦 Stack technique
 
### Backend
![Flask](https://img.shields.io/badge/Flask_2.3-000000?style=flat&logo=flask&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=flat&logo=python&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy_2.0-D71F00?style=flat&logo=sqlalchemy&logoColor=white)
![Socket.IO](https://img.shields.io/badge/Socket.io-black?style=flat&logo=socket.io)
![JWT](https://img.shields.io/badge/JWT-000000?style=flat&logo=jsonwebtokens&logoColor=white)
 
### Frontend
![Next.js](https://img.shields.io/badge/Next.js_15-000000?style=flat&logo=next.js&logoColor=white)
![React](https://img.shields.io/badge/React_19-20232A?style=flat&logo=react&logoColor=61DAFB)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS_3-38B2AC?style=flat&logo=tailwind-css&logoColor=white)
![Framer Motion](https://img.shields.io/badge/Framer_Motion-black?style=flat&logo=framer&logoColor=blue)
 
### Services & Infrastructure
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=flat&logo=supabase&logoColor=white)
![Cloudinary](https://img.shields.io/badge/Cloudinary-3448C5?style=flat&logo=cloudinary&logoColor=white)
![Stripe](https://img.shields.io/badge/Stripe-626CD9?style=flat&logo=Stripe&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat&logo=github-actions&logoColor=white)
 
---
 
## 🔄 CI/CD – GitHub Actions

Le pipeline CI/CD s'exécute automatiquement à chaque push sur `main`.
Il comporte cinq jobs :

| Job                        | Durée  | Description                                               |
|----------------------------|--------|-----------------------------------------------------------|
| Tests Unitaires            | ~29s   | `pytest tests/test_unit_*.py` sur Python 3.11            |
| Tests d'Intégration        | ~28s   | `pytest tests/test_integration_*.py`                     |
| Backend Syntax Check       | ~11s   | Vérification syntaxique `py_compile app.py`              |
| Frontend Build             | ~57s   | `npm run build` sur Node.js 20                           |
| Docker Build & Health Check| ~2-3min| Build des images, démarrage des conteneurs, vérification réelle de `/api/health` et du port 3000 |
 
---
 
## 📞 Support
 
Pour toute question ou problème :
- 🐛 Issues : [GitHub Issues](https://github.com/havenito/Twitter_Like/issues)
---
 
*Développé par Enzo MARTINEZ – Projet CDA RNCP37873 – École Hexagone 2026*

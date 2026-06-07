
# ── Étape 1 : installation des dépendances ───────────────────────────────────
FROM node:20-alpine AS deps
 
WORKDIR /app
 
# Copie des fichiers de dépendances uniquement
COPY package.json package-lock.json ./
 
# Installation propre des dépendances
RUN npm ci
 
# ── Étape 2 : build de l'application ─────────────────────────────────────────
FROM node:20-alpine AS builder
 
WORKDIR /app
 
# Récupère les node_modules de l'étape précédente
COPY --from=deps /app/node_modules ./node_modules
 
# Copie du code source complet
COPY . .
 
# Variables d'environnement nécessaires au build Next.js
# (valeurs factices pour le build – les vraies sont injectées au runtime)
ARG NEXT_PUBLIC_FLASK_API_URL=http://localhost:5000
ARG NEXT_PUBLIC_API_URL=http://localhost:5000
ARG NEXT_PUBLIC_WEBSOCKET_URL=http://localhost:5000
ARG NEXT_PUBLIC_SUPABASE_URL=https://placeholder.supabase.co
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY=placeholder
 
ENV NEXT_PUBLIC_FLASK_API_URL=$NEXT_PUBLIC_FLASK_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WEBSOCKET_URL=$NEXT_PUBLIC_WEBSOCKET_URL
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
 
RUN npm run build
 
# ── Étape 3 : image de production légère ─────────────────────────────────────
FROM node:20-alpine AS runner
 
WORKDIR /app
 
ENV NODE_ENV=production
 
# Copie uniquement ce qui est nécessaire à l'exécution
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
 
# Expose le port Next.js
EXPOSE 3000
 
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
 
CMD ["node", "server.js"]
# 🚀 Guide de Déploiement Production — JARVIS AI

## Phase 1: Préparation du Serveur

### 1.1 Prérequis
```bash
# Installer Docker + Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt-get install -y docker-compose-plugin

# Vérifier
docker --version
docker compose version
```

### 1.2 Cloner le Projet
```bash
git clone <your-repo> /opt/jarvis
cd /opt/jarvis/backend
```

---

## Phase 2: Configuration Production

### 2.1 Générer les Clés Secrètes
```bash
# SECRET_KEY
openssl rand -hex 32
# Output: 6f7e160cb8f94165c098dbaad8076610bf61fc1048d3493f8d9acd9e1395f88a

# ENCRYPTION_KEY
openssl rand -hex 32
# Output: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6

# REDIS_PASSWORD
openssl rand -hex 16
# Output: 7a8b9c0d1e2f3g4h
```

### 2.2 Créer .env.prod
```bash
cp .env.prod.example .env.prod
# Éditer avec vos valeurs
nano .env.prod
```

**Exemple rempli:**
```env
# --- Application ---
APP_NAME=JARVIS AI
APP_ENV=production
DEBUG=false

# --- Sécurité (à générer avec openssl rand -hex 32)
SECRET_KEY=6f7e160cb8f94165c098dbaad8076610bf61fc1048d3493f8d9acd9e1395f88a
ENCRYPTION_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

# --- Base de données (CHANGE PASSWORD!)
DATABASE_URL=postgresql+asyncpg://jarvis:VOTRE_PASSWORD_SECURISE@db:5432/jarvis_db
POSTGRES_USER=jarvis
POSTGRES_PASSWORD=VOTRE_PASSWORD_SECURISE
POSTGRES_DB=jarvis_db

# --- Redis (CHANGE PASSWORD!)
REDIS_URL=redis://:7a8b9c0d1e2f3g4h@redis:6379/0
REDIS_PASSWORD=7a8b9c0d1e2f3g4h

# --- Fournisseurs IA (OBLIGATOIRES)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
ELEVENLABS_API_KEY=...
OLLAMA_BASE_URL=http://ollama:11434

# --- OAuth Google (Enregistrer dans Google Cloud Console)
GOOGLE_OAUTH_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-...
GOOGLE_OAUTH_REDIRECT_URI=https://api.votre-domaine.com/api/v1/auth/google/callback

# --- CORS (Restreindre en production!)
ALLOWED_ORIGINS=https://app.votre-domaine.com,https://www.votre-domaine.com
```

### 2.3 Sécuriser .env.prod
```bash
chmod 600 .env.prod  # Lecture seule par le propriétaire
```

---

## Phase 3: Reverse Proxy (HTTPS)

### Option A: Caddy (Recommandé - Zéro Config HTTPS)

```bash
# Installer Caddy
sudo apt-get install -y caddy

# Créer Caddyfile
sudo nano /etc/caddy/Caddyfile
```

**Contenu:**
```caddyfile
api.votre-domaine.com {
    reverse_proxy localhost:8000 {
        header_uri -accept-encoding
        health_uri /api/v1/health
        health_interval 10s
        health_timeout 5s
    }
}

# Optional: Rediriger HTTP vers HTTPS (Caddy le fait automatiquement)
http://votre-domaine.com {
    redir https://votre-domaine.com{uri} permanent
}
```

```bash
# Relancer Caddy
sudo systemctl restart caddy
sudo systemctl status caddy
```

### Option B: Nginx + Certbot (Plus contrôle)

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx

# Configuration Nginx
sudo nano /etc/nginx/sites-available/jarvis
```

**Contenu:**
```nginx
upstream jarvis_backend {
    server localhost:8000;
}

server {
    listen 80;
    server_name api.votre-domaine.com;

    location / {
        proxy_pass http://jarvis_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    location /api/v1/health {
        proxy_pass http://jarvis_backend;
        access_log off;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/jarvis /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Générer certificat HTTPS
sudo certbot --nginx -d api.votre-domaine.com
```

---

## Phase 4: Démarrage Production

### 4.1 Première Exécution
```bash
cd /opt/jarvis/backend

# Créer répertoire backups
mkdir -p backups

# Démarrer tous les services
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Vérifier que tout fonctionne
docker compose -f docker-compose.prod.yml ps
```

**Output attendu:**
```
NAME                  STATUS
jarvis-backend-prod   Up (healthy)
jarvis-db-prod        Up (healthy)
jarvis-redis-prod     Up
```

### 4.2 Appliquer les Migrations
```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### 4.3 Vérifier la Santé
```bash
# Via le reverse proxy
curl https://api.votre-domaine.com/api/v1/health

# Réponse attendue:
# {"status": "ok", "service": "JARVIS AI backend"}

# Ou directement
curl http://localhost:8000/api/v1/health
```

---

## Phase 5: Monitoring & Maintenance

### 5.1 Logs
```bash
# Backend
docker compose -f docker-compose.prod.yml logs -f backend

# PostgreSQL
docker compose -f docker-compose.prod.yml logs -f db

# Redis
docker compose -f docker-compose.prod.yml logs -f redis
```

### 5.2 Sauvegarde Automatisée (Cron)
```bash
# Ajouter à crontab
sudo crontab -e

# Ajouter cette ligne (3h du matin quotidiennement)
0 3 * * * cd /opt/jarvis/backend && bash backup.sh >> /var/log/jarvis_backup.log 2>&1
```

### 5.3 Vérifier les Backups
```bash
ls -lh /opt/jarvis/backend/backups/
# jarvis_20250908_030000.sql.gz (245M)
# jarvis_20250907_030000.sql.gz (243M)
```

### 5.4 Restaurer depuis une Sauvegarde
```bash
# Décompresser et restaurer
gunzip -c backups/jarvis_20250908_030000.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U jarvis jarvis_db
```

---

## Phase 6: Montée en Charge (Multi-instance)

Si vous avez besoin de plus de capacité:

```yaml
# docker-compose.prod.yml
backend:
  deploy:
    replicas: 3  # Lancer 3 instances
  environment:
    # Workers Gunicorn réduits par instance
    WORKERS=2
```

Puis ajouter un load balancer devant:
- **Nginx**: `upstream backend { server backend:8000; server backend:8001; ... }`
- **Traefik**: Labels automatiques (recommandé pour Docker Swarm/Kubernetes)

---

## Phase 7: Checklist Final

- [ ] Domain DNS pointe vers le serveur
- [ ] Reverse proxy (Caddy/Nginx) configuré
- [ ] HTTPS/certificat LetsEncrypt fonctionnel
- [ ] `.env.prod` rempli avec tous les secrets
- [ ] Conteneurs démarrent sans erreur
- [ ] Healthcheck `GET /api/v1/health` répond 200
- [ ] Logs propres (pas d'erreurs)
- [ ] Backups PostgreSQL en place
- [ ] Monitoring actif
- [ ] Alertes configurées (Sentry, etc.)

---

## 🆘 Troubleshooting

### "Error: Connection refused"
```bash
# Vérifier que les containers tournent
docker compose -f docker-compose.prod.yml ps

# Vérifier les logs
docker compose -f docker-compose.prod.yml logs backend
```

### "Database 'jarvis_db' does not exist"
```bash
# Réappliquer les migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### "502 Bad Gateway (Nginx/Caddy)"
```bash
# Vérifier que le backend répond
curl http://localhost:8000/api/v1/health

# Redémarrer le backend
docker compose -f docker-compose.prod.yml restart backend
```

### "Out of Memory"
```bash
# Augmenter les limites dans docker-compose.prod.yml
deploy:
  resources:
    limits:
      memory: 4G  # Augmenter de 2G à 4G
```

---

## 📊 Performance Attendue

Avec la config prod standard:
- **Requêtes/sec**: 100-500 (selon la charge des workers IA)
- **Latence API**: 50-200ms
- **Utilisation RAM**: 800MB-1.5GB
- **Utilisation CPU**: 10-40%
- **Uptime**: >99.5%

---

## 📞 Support

Voir `ANALYSIS_REPORT.md` pour les recommandations de sécurité et future.

---

**Dernière mise à jour:** 2025-09-08  
**Auteur:** Gordon (Docker Assistant)

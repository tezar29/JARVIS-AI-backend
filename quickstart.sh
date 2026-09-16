#!/bin/bash
# quickstart.sh — Démarrage rapide du backend JARVIS AI

set -e

echo "🚀 JARVIS AI Backend - Quick Start"
echo "=================================="
echo ""

# Vérifier Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

# Vérifier Docker Compose
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose not found. Please install it:"
    echo "   https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker et Docker Compose détectés"
echo ""

# Mode de démarrage
if [ "$1" == "prod" ]; then
    MODE="production"
    COMPOSE_FILE="docker-compose.prod.yml"
    ENV_FILE=".env.prod"
else
    MODE="development"
    COMPOSE_FILE="docker-compose.yml"
    ENV_FILE=".env"
fi

echo "Mode: $MODE"
echo ""

# Vérifier fichier .env
if [ "$MODE" == "production" ] && [ ! -f "$ENV_FILE" ]; then
    echo "⚠️  Fichier $ENV_FILE manquant!"
    echo "   Créer avec: cp .env.prod.example .env.prod"
    echo "   Puis éditer et ajouter les clés"
    exit 1
fi

echo "🛑 Arrêt des services existants..."
if [ "$MODE" == "production" ]; then
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down 2>/dev/null || true
else
    docker compose down 2>/dev/null || true
fi

echo ""
echo "🐳 Démarrage des services Docker..."
if [ "$MODE" == "production" ]; then
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
else
    docker compose up -d --build
fi

echo ""
echo "⏳ Attente du démarrage (10s)..."
sleep 10

echo ""
echo "🔄 Appliquant les migrations Alembic..."
if [ "$MODE" == "production" ]; then
    docker compose -f "$COMPOSE_FILE" exec backend alembic upgrade head
else
    docker compose exec backend alembic upgrade head
fi

echo ""
echo "✅ Vérification de la santé..."
if [ "$MODE" == "production" ]; then
    docker compose -f "$COMPOSE_FILE" ps
else
    docker compose ps
fi

echo ""
echo "🔍 Test de l'API..."
HEALTH=$(docker compose exec backend python -c "import httpx; r = httpx.get('http://localhost:8000/api/v1/health'); print(r.status_code)" 2>/dev/null)

if [ "$HEALTH" == "200" ]; then
    echo "✅ API répond correctement (200 OK)"
else
    echo "⚠️  API ne répond pas comme attendu"
fi

echo ""
echo "=================================="
echo "🎉 Démarrage réussi!"
echo "=================================="
echo ""
echo "📋 Prochaines étapes:"
echo ""
echo "Développement:"
echo "  • API: http://localhost:8000"
echo "  • Swagger: http://localhost:8000/docs"
echo "  • Logs: docker compose logs -f backend"
echo ""
echo "Base de données:"
echo "  • Host: localhost:5432"
echo "  • User: jarvis"
echo "  • DB: jarvis_db"
echo ""
echo "Redis:"
echo "  • Host: localhost:6379"
echo ""
echo "Commandes utiles:"
echo "  • Stop: docker compose down"
echo "  • Logs: docker compose logs -f backend"
echo "  • Shell: docker compose exec backend bash"
echo "  • DB: docker compose exec db psql -U jarvis -d jarvis_db"
echo ""

if [ "$MODE" == "production" ]; then
    echo "⚠️  Mode Production Active"
    echo "  • Voir PRODUCTION_SETUP.md pour plus de détails"
fi

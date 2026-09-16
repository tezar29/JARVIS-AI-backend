#!/bin/bash
# backup.sh — Sauvegarde quotidienne automatisée PostgreSQL

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"

# Créer le répertoire s'il n'existe pas
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Démarrage de la sauvegarde PostgreSQL..."

# Dumper la base de données
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U jarvis jarvis_db | gzip > "$BACKUP_DIR/jarvis_${TIMESTAMP}.sql.gz"

echo "[$(date)] ✅ Sauvegarde créée: jarvis_${TIMESTAMP}.sql.gz"

# Conserver seulement les 14 derniers jours
find "$BACKUP_DIR" -name "jarvis_*.sql.gz" -mtime +14 -delete

echo "[$(date)] ✅ Vieilles sauvegardes supprimées (>14 jours)"
echo "[$(date)] Sauvegarde terminée."

# Afficher les sauvegardes disponibles
echo ""
echo "=== Sauvegardes disponibles ==="
ls -lh "$BACKUP_DIR" | grep -v "^total" | awk '{print $9, "(" $5 ")"}'

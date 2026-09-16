FROM python:3.12-slim

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx, os; httpx.get('http://localhost:' + os.getenv('PORT', '10000') + '/api/v1/health', timeout=5)" || exit 1

# Render fournit la variable PORT au démarrage du conteneur.
# Le shell est utilisé ici uniquement pour permettre l'expansion de PORT.
CMD ["sh", "-c", "exec gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-10000} --timeout 120 --access-logfile - --error-logfile -"]

#!/bin/bash
# Render-compatible startup script

set -e

echo "🚀 JARVIS AI Backend Startup Script"
echo "App environment: $APP_ENV"

# Change to backend directory (where app.main is located)
cd backend

# Ensure we have a PORT variable
PORT=${PORT:-8000}
echo "Binding to port: $PORT"

# Check if running on Render (production) or locally (development)
if [ "$APP_ENV" = "production" ] || [ "$RENDER" = "true" ]; then
    echo "📦 Running in PRODUCTION mode (Gunicorn)"
    
    # Apply migrations
    echo "🔄 Running Alembic migrations..."
    alembic upgrade head
    
    # Start with gunicorn
    exec gunicorn app.main:app \
        --workers 2 \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:$PORT \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -
else
    echo "🔧 Running in DEVELOPMENT mode (Uvicorn with --reload)"
    
    # Development with reload
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --reload
fi

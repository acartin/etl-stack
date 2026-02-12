#!/bin/bash
# Matar procesos existentes
pkill -f "uvicorn src.api.main:app"
pkill -f "python3 -m src.worker_service"

sleep 2

# Definir rutas de logs (absolutas para evitar líos)
API_LOG="/app/src/api_status.log"
WORKER_LOG="/app/src/worker_status.log"

export PYTHONPATH=$PYTHONPATH:/app

echo "Reiniciando API desde /app..."
cd /app
nohup /usr/bin/python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 > $API_LOG 2>&1 &

echo "Reiniciando Worker desde /app..."
nohup /usr/bin/python3 -m src.worker_service > $WORKER_LOG 2>&1 &

echo "Servicios reiniciados. Logs en $API_LOG y $WORKER_LOG"

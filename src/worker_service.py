
import os
import sys
import logging
from dotenv import load_dotenv

# 1. Configurar Entorno ANTES de importar nada más
# Esto asegura que os.getenv funcione en todos los módulos importados
load_dotenv("/app/src/.env")

# Asegurar que el path del proyecto está en sys.path
sys.path.append("/app/src")

from redis import Redis
from rq import Worker, Queue

# Configurar Logging básico para el worker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - WORKER - %(levelname)s - %(message)s'
)

listen = ['etl_queue']
conn = Redis(host='localhost', port=6379, db=0)

if __name__ == '__main__':
    print("👷 Iniciando Worker de RQ. Escuchando colas: etl_queue")
    
    # Crear instancias de Queue con conexión explícita
    queues = [Queue(name, connection=conn) for name in listen]
    worker = Worker(queues, connection=conn)
    worker.work()

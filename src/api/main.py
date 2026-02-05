
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv("/app/src/.env")

# Importar Routers
from src.api.routers import docs

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Inicializar App
app = FastAPI(
    title="Agentic ETL Platform API",
    description="API unificada para procesamiento de propiedades, documentos y POIs.",
    version="1.0.0"
)

# Configurar CORS (Permitir todo por ahora para desarrollo interno)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir Routers
from fastapi.staticfiles import StaticFiles

# Incluir Routers
app.include_router(docs.router)

from src.BRAND_CONFIG.router import router as brand_router
app.include_router(brand_router)

# Mount Storage for Images
if os.path.exists("/app/data/storage"):
    app.mount("/storage", StaticFiles(directory="/app/data/storage"), name="storage")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Agentic ETL Platform"}

if __name__ == "__main__":
    import uvicorn
    # Ejecución directa para pruebas (python main.py)
    uvicorn.run(app, host="0.0.0.0", port=8000)

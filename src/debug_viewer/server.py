import os
import uvicorn
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv("/app/src/.env")

app = FastAPI(title="Image Debugger", docs_url=None, redoc_url=None)

# 1. Montar directorio de imágenes estáticas
# Esto permite acceder a /app/storage/images usando la URL http://.../images/
STORAGE_ROOT = "/app/storage/images"
app.mount("/images", StaticFiles(directory=STORAGE_ROOT), name="images")

# 2. Configurar Templates
templates = Jinja2Templates(directory="/app/src/debug_viewer/templates")

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "192.168.0.31"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "agentic"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        cursor_factory=RealDictCursor
    )

def get_file_size_kb(relative_path):
    """Calcula el tamaño del archivo en disco si existe."""
    try:
        full_path = os.path.join(STORAGE_ROOT, relative_path)
        if os.path.exists(full_path):
            return int(os.path.getsize(full_path) / 1024)
        return 0
    except:
        return 0

@app.get("/", response_class=HTMLResponse)
async def list_properties(request: Request, client_id: str = None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # A. Obtener lista de clientes para el selector
            # Hacemos un JOIN directo para obtener nombre real y provider
            cur.execute("""
                SELECT 
                    c.id as client_id, 
                    c.name as client_name,
                    COALESCE(ss.provider_type, 'Unknown') as provider_type
                FROM public.lead_clients c
                JOIN public.stage_sources_config ss ON c.id = ss.client_id
                ORDER BY c.name
            """)
            clients = cur.fetchall()
            
            # B. Construir Query de Propiedades con Filtro
            query = """
                SELECT 
                    p.id, p.title, p.price, p.currency_id as currency, p.client_id, p.public_url,
                    p.poi_data, p.location_lat, p.location_lng
                FROM public.lead_properties p
                WHERE EXISTS (SELECT 1 FROM public.lead_property_images i WHERE i.property_id = p.id)
                AND p.price > 0
            """
            params = []
            
            if client_id and client_id != "all":
                query += " AND p.client_id = %s"
                params.append(client_id)
            
            query += " LIMIT 50"
            
            cur.execute(query, tuple(params))
            properties = cur.fetchall()
            
            enriched_props = []
            for p in properties:
                prop_id = p['id']
                cur.execute("""
                    SELECT local_path, is_main, sort_order, vision_labels
                    FROM public.lead_property_images
                    WHERE property_id = %s
                    ORDER BY sort_order ASC
                """, (prop_id,))
                
                images = []
                for img in cur.fetchall():
                    size = get_file_size_kb(img['local_path'])
                    filename = os.path.basename(img['local_path'])
                    
                    # Parsear JSON si viene como string (psycopg2 suele dar dict con Json wrapper, pero aseguramos)
                    tags = img['vision_labels']
                    # Si es None o vacío, pasamos None
                    
                    images.append({
                        "local_path": img['local_path'],
                        "is_main": img['is_main'],
                        "sort_order": img['sort_order'],
                        "size_kb": size,
                        "filename": filename,
                        "tags": tags 
                    })
                
                p['images'] = images
                enriched_props.append(p)
                
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "properties": enriched_props,
            "clients": clients,
            "current_client": client_id
        })
    finally:
        conn.close()

if __name__ == "__main__":
    # Correr en puerto 8000 accesible desde fuera
    uvicorn.run(app, host="0.0.0.0", port=8001)

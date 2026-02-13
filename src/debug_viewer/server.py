import os
import uvicorn
import psycopg2
import hashlib
import hmac
import datetime
import urllib.parse
import requests
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.responses import Response
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv("/app/src/.env")

app = FastAPI(title="Image Debugger", docs_url=None, redoc_url=None)

# 1. Backend de storage para el viewer (local o r2)
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()
STORAGE_ROOT = os.getenv("PATH_STORAGE", "/app/data/storage") + "/images"

R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL", "").strip().rstrip("/")
R2_BUCKET = os.getenv("R2_BUCKET", "").strip()
R2_REGION = os.getenv("R2_REGION", "auto").strip()
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
R2_PREFIX = os.getenv("R2_PREFIX", "").strip("/")
R2_IMAGES_PREFIX = os.getenv("R2_IMAGES_PREFIX", "images").strip("/")

if STORAGE_BACKEND == "local":
    # Esto permite acceder a /app/data/storage/images usando la URL http://.../images/
    app.mount("/images", StaticFiles(directory=STORAGE_ROOT), name="images")

# 2. Configurar Templates
templates = Jinja2Templates(directory="/app/src/debug_viewer/templates")

def _r2_sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

def _r2_signing_key(secret: str, date_stamp: str, region: str, service: str = "s3") -> bytes:
    k_date = _r2_sign(("AWS4" + secret).encode("utf-8"), date_stamp)
    k_region = _r2_sign(k_date, region)
    k_service = _r2_sign(k_region, service)
    return _r2_sign(k_service, "aws4_request")

def _r2_object_key(image_path: str) -> str:
    clean = image_path.lstrip("/")
    if R2_PREFIX:
        return f"{R2_PREFIX}/{R2_IMAGES_PREFIX}/{clean}"
    return f"{R2_IMAGES_PREFIX}/{clean}"

def _r2_signed_request(method: str, object_key: str) -> requests.Response:
    if not all([R2_ENDPOINT_URL, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        raise RuntimeError("Faltan variables R2 para STORAGE_BACKEND=r2")

    parsed = urllib.parse.urlparse(R2_ENDPOINT_URL)
    host = parsed.netloc
    path = f"/{R2_BUCKET}/" + urllib.parse.quote(object_key, safe="/-_.~")

    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(b"").hexdigest()
    canonical_query = ""
    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join([
        method,
        path,
        canonical_query,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])
    scope = f"{date_stamp}/{R2_REGION}/s3/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signing_key = _r2_signing_key(R2_SECRET_ACCESS_KEY, date_stamp, R2_REGION)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={R2_ACCESS_KEY_ID}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        "Authorization": authorization,
    }
    url = f"{R2_ENDPOINT_URL}{path}"
    return requests.request(method, url, headers=headers, timeout=30)

@app.get("/images/{image_path:path}")
def get_image_from_storage(image_path: str):
    if STORAGE_BACKEND == "local":
        raise HTTPException(status_code=404, detail="Use static /images mount in local mode.")

    try:
        object_key = _r2_object_key(image_path)
        r = _r2_signed_request("GET", object_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error R2: {e}") from e

    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="Imagen no encontrada en R2")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"R2 status {r.status_code}")

    content_type = r.headers.get("Content-Type", "application/octet-stream")
    return Response(content=r.content, media_type=content_type)

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
    if STORAGE_BACKEND == "r2":
        return 0

    try:
        full_path = os.path.join(STORAGE_ROOT, relative_path)
        if os.path.exists(full_path):
            return int(os.path.getsize(full_path) / 1024)
        return 0
    except:
        return 0

def get_property_images(cur, property_id: str):
    cur.execute("""
        SELECT local_path, is_main, sort_order, vision_labels
        FROM public.lead_property_images
        WHERE property_id = %s
        ORDER BY sort_order ASC
    """, (property_id,))

    images = []
    for img in cur.fetchall():
        size = get_file_size_kb(img["local_path"])
        filename = os.path.basename(img["local_path"])
        images.append({
            "local_path": img["local_path"],
            "image_url": f"/images/{img['local_path']}",
            "is_main": img["is_main"],
            "sort_order": img["sort_order"],
            "size_kb": size,
            "filename": filename,
            "tags": img["vision_labels"],
        })
    return images

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
                p["images"] = get_property_images(cur, prop_id)
                enriched_props.append(p)
                
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "properties": enriched_props,
            "clients": clients,
            "current_client": client_id
        })
    finally:
        conn.close()

@app.get("/property/{property_id}", response_class=HTMLResponse)
async def property_detail(request: Request, property_id: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    p.id, p.title, p.price, p.currency_id as currency, p.client_id,
                    p.public_url, p.poi_data, p.location_lat, p.location_lng,
                    c.name as client_name
                FROM public.lead_properties p
                LEFT JOIN public.lead_clients c ON c.id = p.client_id
                WHERE p.id = %s
                LIMIT 1
            """, (property_id,))
            prop = cur.fetchone()

            if not prop:
                raise HTTPException(status_code=404, detail="Propiedad no encontrada")

            images = get_property_images(cur, property_id)
            prop["images"] = images
            main_image = next((img for img in images if img["is_main"]), images[0] if images else None)

        return templates.TemplateResponse("property_detail.html", {
            "request": request,
            "property": prop,
            "main_image": main_image,
            "storage_backend": STORAGE_BACKEND,
        })
    finally:
        conn.close()

if __name__ == "__main__":
    # Correr en puerto 8000 accesible desde fuera
    uvicorn.run(app, host="0.0.0.0", port=8001)

import os
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv
import logging

# Importar el generador de paquetes existente
# Asegurarse de que el PYTHONPATH incluya /app/src para esta importación
try:
    from ETL_POIS.cl_test1 import generate_lead_prep_package
except ImportError:
    # Fallback si se ejecuta directo
    import sys
    sys.path.append("/app/src")
    from ETL_POIS.cl_test1 import generate_lead_prep_package

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("POI_MATCHER")

# Cargar entorno
load_dotenv("/app/src/.env")

DB_HOST = os.getenv("DB_HOST", "192.168.0.31")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "agentic")
DB_USER = os.getenv("DB_USER", "acartin")
DB_PASS = os.getenv("DB_PASS", "Toyota_15")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=RealDictCursor
    )

def transform_package_to_frontend_json(package):
    """
    Convierte el paquete pesado de análisis en un JSON ligero optimizado para mapas frontend.
    """
    map_features = []
    
    # Colores por categoría (SDUI Style)
    colors = {
        "Education": "#3b82f6",      # blue-500
        "Health": "#ec4899",         # pink-500
        "Convenience": "#22c55e",    # green-500
        "Safety": "#64748b",         # slate-500
        "Restaurant_Cafe": "#f97316",# orange-500
        "Shopping": "#a855f7",       # purple-500
        "Sport_Leisure": "#06b6d4",  # cyan-500
        "Charging_Infrastructure": "#eab308", # yellow-500
        "Nature_Tourism": "#16a34a"  # green-600
    }

    # Fusionar todos los Tiers
    all_pois = {**package['tier_1_critical_pois'], **package['tier_2_lifestyle_pois']}
    # Tier 3 opcional si queremos mapa limpio
    if 'tier_3_nice_to_have_pois' in package:
        all_pois.update(package['tier_3_nice_to_have_pois'])

    count = 0
    for cat, pois in all_pois.items():
        if not pois: continue
        # Limitamos a los top 5 por categoría para no saturar el mapa visual
        for poi in pois[:5]:
            map_features.append({
                "id": poi.get('osm_id'), # Referencia si se quiere linkear
                "lat": poi['lat'],
                "lng": poi['lon'],
                "name": poi['name'],
                "category": cat,
                "distance": f"{poi['distance_km']:.2f} km",
                "score": poi['quality_score'],
                "color": colors.get(cat, "#94a3b8")
            })
            count += 1
            
    summary = {
        "score": package['metrics']['walkability_score'],
        "label": package['metrics']['walkability_label'],
        "premium": package['metrics']['is_premium_zone'],
        "highlights": package['talking_points']['opening_hooks'],
        "map_points": map_features
    }
    
    return summary

def process_batch(batch_size=50):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Seleccionar propiedades con coordenadas validas y SIN poi_data (o viejas)
            # Priorizamos las actualizadas recientemente
            cur.execute("""
                SELECT id, title, location_lat, location_lng 
                FROM public.lead_properties 
                WHERE location_lat IS NOT NULL 
                  AND location_lng IS NOT NULL 
                  AND poi_data IS NULL
                LIMIT %s
            """, (batch_size,))
            
            props = cur.fetchall()
            
            if not props:
                logger.info("😴 No hay propiedades pendientes de análisis POI.")
                return False

            logger.info(f"🚀 Procesando lote de {len(props)} propiedades...")
            
            for p in props:
                try:
                    logger.info(f"📍 Analizando: {p['title'][:30]}... ({p['location_lat']}, {p['location_lng']})")
                    
                    # 1. Generar Paquete Completo (Lógica Pesada)
                    full_package = generate_lead_prep_package(
                        property_lat=float(p['location_lat']),
                        property_lon=float(p['location_lng']),
                        output_file=None # No guardar archivo físico
                    )
                    
                    # 2. Transformar a JSON Ligero
                    frontend_json = transform_package_to_frontend_json(full_package)
                    
                    # 3. Guardar en DB
                    cur.execute("""
                        UPDATE public.lead_properties
                        SET poi_data = %s
                        WHERE id = %s
                    """, (Json(frontend_json), p['id']))
                    
                    conn.commit() # Commit por propiedad para robustez en batch
                    
                except Exception as e:
                    logger.error(f"❌ Error en propiedad {p['id']}: {e}")
                    conn.rollback()
            
            return True

    except Exception as e:
        logger.error(f"❌ Error general DB: {e}")
        return False
    finally:
        conn.close()

def run_loop():
    logger.info("🔄 Iniciando ciclo de POI Matching...")
    while True:
        has_work = process_batch(batch_size=20)
        if not has_work:
            logger.info("✅ Todo procesado. Terminando.")
            break
        time.sleep(1)

if __name__ == "__main__":
    run_loop()

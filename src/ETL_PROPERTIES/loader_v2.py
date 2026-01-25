import os
import json
import uuid
import hashlib
import psycopg2
import re
from datetime import datetime
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FUNCIONES DE LIMPIEZA (Lógica de Negocio en Python) ---

def clean_price(val, currency_raw):
    if not val: return 0, currency_raw
    s = str(val).strip().replace(',', '.')
    s_clean = re.sub(r'[^0-9.]', '', s)
    if s_clean.count('.') > 1:
        parts = s_clean.split('.')
        s_clean = f"{''.join(parts[:-1])}.{parts[-1]}"
    try:
        num = float(s_clean)
        # Limite Numeric(15,2)
        if num > 9999999999999.99: return 0, 'USD'
        
        # Validar y limpiar moneda inicial
        final_currency = str(currency_raw).strip().upper()[:3] if currency_raw else 'USD'
        if final_currency not in ['USD', 'CRC']:
            final_currency = 'USD'

        # Heurística de moneda
        if num > 1000000:
            final_currency = 'CRC'
            
        return num, final_currency
    except:
        return 0, 'USD'

def clean_area(val):
    if not val: return None
    s = str(val).strip().replace(',', '.')
    s_clean = re.sub(r'[^0-9.]', '', s)
    try:
        num = float(s_clean)
        if num <= 0 or num > 9999999.99: return None 
        return num
    except:
        return None

def clean_smallint(val, max_limit=30000):
    if not val: return None
    match = re.search(r'(\d+)', str(val))
    if not match: return None
    try:
        num = int(match.group(1))
        return num if num <= max_limit else None
    except:
        return None

def clean_numeric_small(val, max_limit=99.9):
    if not val: return None
    s = str(val).strip().replace(',', '.')
    s_clean = re.sub(r'[^0-9.]', '', s)
    try:
        num = float(s_clean)
        return num if num <= max_limit else None
    except:
        return None

# --- MAIN LOADER ---

def get_db_connection():
    load_dotenv("/app/src/.env")
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )

def calculate_content_hash(item):
    hash_content = f"{item.get('title')}|{item.get('price')}|{item.get('currency')}|{item.get('sqm')}|{item.get('location', {}).get('lat')}|{item.get('location', {}).get('lng')}"
    return hashlib.sha256(hash_content.encode('utf-8')).hexdigest()

def process_file(filepath, conn):
    batch_id = str(uuid.uuid4())
    logger.info(f"🚀 Procesando archivo: {os.path.basename(filepath)}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    client_id = data.get("metadata", {}).get("client_id")
    if not client_id: return

    properties = data.get("properties", [])
    cleaned_rows = []
    
    for p in properties:
        # Filtro Status (WordPress o similar)
        # Buscamos en raiz o en raw_data
        status = p.get("status") or p.get("raw_data_snapshot", {}).get("status", "active")
        if str(status).lower() not in ['publish', 'active', 'published']:
            continue
            
        clean_p, clean_curr = clean_price(p.get("price"), p.get("currency"))
        clean_sqm = clean_area(p.get("sqm") or p.get("features", {}).get("sqm"))
        clean_beds = clean_smallint(p.get("features", {}).get("bedrooms"), 100)
        clean_baths = clean_numeric_small(p.get("features", {}).get("bathrooms"), 99)
        
        feats = p.get("features", {})
        feats['sqm_clean'] = clean_sqm
        feats['bedrooms_clean'] = clean_beds
        feats['bathrooms_clean'] = clean_baths
        
        raw_desc = ""
        if "raw_data_snapshot" in p and "content" in p["raw_data_snapshot"]:
             raw_desc = str(p["raw_data_snapshot"]["content"].get("rendered", ""))
        
        content_hash = calculate_content_hash(p)
        
        cleaned_rows.append((
            batch_id,
            client_id,
            str(p.get("external_id")),
            p.get("url"),
            (p.get("title") or "Sin Título")[:250],
            str(clean_p),
            str(clean_curr),
            raw_desc,
            json.dumps(p.get("location")),
            json.dumps(feats),
            json.dumps(p.get("images", [])),
            json.dumps(p.get("raw_data_snapshot", {})),
            content_hash
        ))
    
    cur = conn.cursor()
    try:
        # 1. Insert Stage
        insert_query = """
            INSERT INTO public.stage_properties (
                batch_id, client_id, external_prop_id, 
                url, title, price_raw, currency_raw, 
                description_raw, location_json, features_json, 
                images_json, raw_snapshot, content_hash
            ) VALUES %s
        """
        from psycopg2.extras import execute_values
        execute_values(cur, insert_query, cleaned_rows)
        
        # 2. Merge Final a lead_properties
        # Mapeo exacto basado en el esquema real de la tabla
        merge_sql = """
        INSERT INTO public.lead_properties (
            client_id, external_prop_id, title, public_url, 
            price, currency_id, area_sqm, bedrooms, bathrooms,
            location_lat, location_lng, address_street, 
            description, features, status, content_hash, 
            created_at, updated_at, property_type_id
        )
        SELECT 
            s.client_id, s.external_prop_id, s.title, s.url,
            NULLIF(s.price_raw, 'None')::NUMERIC,
            s.currency_raw,
            (s.features_json->>'sqm_clean')::NUMERIC, 
            (s.features_json->>'bedrooms_clean')::SMALLINT,
            (s.features_json->>'bathrooms_clean')::NUMERIC,
            NULLIF((s.location_json->>'lat'), '')::NUMERIC,
            NULLIF((s.location_json->>'lng'), '')::NUMERIC,
            (s.location_json->>'address'), -- address_street
            s.description_raw,
            s.features_json,
            'active',
            s.content_hash,
            NOW(), NOW(),
            CASE 
                WHEN POSITION('lote' IN LOWER(s.title)) > 0 THEN 3
                WHEN POSITION('apartamento' IN LOWER(s.title)) > 0 THEN 2
                ELSE 1
            END
        FROM public.stage_properties s
        WHERE s.batch_id = %(batch_id)s
        ON CONFLICT (client_id, external_prop_id) DO UPDATE SET
            updated_at = NOW(), -- Siempre marcamos como verificado
            title = EXCLUDED.title,
            price = EXCLUDED.price,
            content_hash = EXCLUDED.content_hash,
            status = 'active',
            property_type_id = EXCLUDED.property_type_id
        WHERE lead_properties.content_hash IS DISTINCT FROM EXCLUDED.content_hash 
           OR lead_properties.status = 'deleted';
        """
        cur.execute(merge_sql, {'batch_id': batch_id})
        logger.info(f"✅ {os.path.basename(filepath)}: {cur.rowcount} sincronizados.")

        # 3. Soft Delete
        delete_sql = """
        UPDATE public.lead_properties
        SET status = 'deleted', updated_at = NOW()
        WHERE client_id = %(client_id)s
          AND status != 'deleted'
          AND external_prop_id NOT IN (
              SELECT external_prop_id FROM public.stage_properties WHERE batch_id = %(batch_id)s
          );
        """
        cur.execute(delete_sql, {'client_id': client_id, 'batch_id': batch_id})

        
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error en {os.path.basename(filepath)}: {e}")
    finally:
        cur.close()

def main():
    conn = get_db_connection()
    output_dir = "/app/src/ETL_PROPERTIES/output"
    files = sorted([f for f in os.listdir(output_dir) if f.endswith('.json')])
    for f in files:
        process_file(os.path.join(output_dir, f), conn)
    conn.close()

if __name__ == "__main__":
    main()

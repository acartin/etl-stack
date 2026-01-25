import geopandas as gpd
import pandas as pd
import os
import sys
import hashlib
import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv
import json
from shapely.ops import unary_union
from shapely.geometry import Point
import re
import unicodedata
from difflib import SequenceMatcher

# --- CONFIGURACIÓN DE RUTAS E INFRAESTRUCTURA ---
load_dotenv("/app/src/.env")

# Rutas y Nombres de Tabla (Hardcoded o Env)
INPUT_PBF = "/app/staging/data_raw/costa-rica-latest.osm.pbf"
TABLE_NAME = "stage_pois_osm"

# --- CONFIGURACIÓN TÉCNICA (Constantes) ---
SPATIAL_CONFIG = {
    "unification_radius_meters": 20,
    "crs_meters": "EPSG:5367",
    "crs_output": "EPSG:4326"
}

QUALITY_WEIGHTS = {
    "has_osm_tag": 10,
    "has_real_name": 5,
    "is_known_brand": 15,
    "metadata_richness": 3
}

# --- CARGAR CONFIGURACIÓN DE REGLAS DE NEGOCIO ---
CONFIG_PATH = "/app/src/ETL_POIS/config_poi_filtering.json"
TOPBRANDS_PATH = "/app/src/ETL_POIS/topbrands.json"

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print(f"❌ ERROR: No se encontró {CONFIG_PATH}")
        sys.exit(1)

CONFIG = load_config()

# Extraer configuraciones de lógica de negocio
TAGS_INTERES = CONFIG['osm']['tags_of_interest']
POI_CATEGORIES = CONFIG['poi_categories']

# Cargar MAPEO DE MARCAS (Top Brands)
KNOWN_BRANDS_MAP = {} # { "OSM Name": "Ideal Brand" }
IDEAL_BRANDS_LIST = [] # [ "Ideal Brand 1", "Ideal Brand 2" ]

if os.path.exists(TOPBRANDS_PATH):
    with open(TOPBRANDS_PATH, 'r') as f:
        tb_data = json.load(f)
        mappings = tb_data.get("brand_mappings", {})
        for cat, brands_dict in mappings.items():
            for ideal, osm_name in brands_dict.items():
                if osm_name:
                    KNOWN_BRANDS_MAP[osm_name.lower()] = ideal
                IDEAL_BRANDS_LIST.append(ideal)
    print(f"✅ Cargadas {len(IDEAL_BRANDS_LIST)} marcas premium desde topbrands.json")
else:
    print("⚠️ No se encontró topbrands.json!")
    IDEAL_BRANDS_LIST = []

# --- CONFIGURACIÓN DB ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "agentic")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")

DB_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- FUNCIONES AUXILIARES ---

def generate_poi_hash(name, category, lat, lon):
    unique_str = f"{name}|{category}|{lat:.6f}|{lon:.6f}"
    return hashlib.sha256(unique_str.encode()).hexdigest()

def normalize_text(text):
    """Elimina tildes y convierte a minúsculas para comparaciones robustas."""
    if not isinstance(text, str): 
        return ""
    text = unicodedata.normalize('NFD', text)
    text = "".join([c for c in text if unicodedata.category(c) != 'Mn'])
    return text.lower()

def parse_all_tags(row):
    """Combina columnas explícitas y other_tags en un solo dict para clasificación."""
    tags = {}
    for col in TAGS_INTERES:
        if col in row and pd.notnull(row[col]):
            tags[col] = str(row[col]).lower()
    
    if 'other_tags' in row and isinstance(row['other_tags'], str):
        try:
            parts = row['other_tags'].split(',')
            for p in parts:
                if '=>' in p:
                    k, v = p.split('=>')
                    tags[k.strip('" ')] = v.strip('" ').lower()
        except: 
            pass
    return tags

# --- FUZZY MATCHING HELPERS ---
def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_brand_fuzzy(name, whitelist, threshold=0.85):
    """Encuentra si el nombre coincide con alguna marca de la whitelist usando fuzzy matching."""
    if not name: return None
    
    # 1. Búsqueda Directa (Rápida)
    for brand in whitelist:
        if brand.lower() in name.lower():
            return brand

    # 2. Búsqueda Fuzzy (Más lenta pero potente)
    best_match = None
    best_score = 0
    
    for brand in whitelist:
        if abs(len(name) - len(brand)) > len(brand) * 0.5:
            continue
            
        score = similar(name, brand)
        if score > best_score:
            best_score = score
            best_match = brand
            
    if best_score >= threshold:
        return best_match
    return None

def detect_brand_smart(name, tags):
    """Detecta la marca ideal basada en nombre OSM o tags."""
    # 1. Si viene brand explícito en tag
    if 'brand' in tags:
        orig = tags['brand'].title()
        # Verificar si podemos mapear este brand explícito a uno ideal
        if orig.lower() in KNOWN_BRANDS_MAP:
             return KNOWN_BRANDS_MAP[orig.lower()]
        return orig
        
    if not name: return None
    name_lower = name.lower()
    
    # 2. Mapeo Exacto (Prioridad Máxima - topbrands.json)
    if name_lower in KNOWN_BRANDS_MAP:
        return KNOWN_BRANDS_MAP[name_lower]
        
    # 3. Contenido Parcial (Mapeo Inverso)
    for osm_name, ideal in KNOWN_BRANDS_MAP.items():
        if osm_name.lower() in name_lower:
            return ideal
            
    # 4. Fuzzy Match Clásico
    fuzzy = find_brand_fuzzy(name, IDEAL_BRANDS_LIST, threshold=0.90)
    if fuzzy:
        return fuzzy
        
    return None

def extract_brand(name, tags):
    """Interfaz unificada para extracción de marca."""
    return detect_brand_smart(name, tags)

def calculate_quality_score(row, category, tags, has_real_name, brand):
    """Calcula score de calidad del POI."""
    score = 0
    
    if tags.get('amenity') or tags.get('shop') or tags.get('leisure'):
        score += QUALITY_WEIGHTS['has_osm_tag']
    
    if has_real_name:
        score += QUALITY_WEIGHTS['has_real_name']
    else:
        score -= 5
        
    if brand in IDEAL_BRANDS_LIST:
        score += QUALITY_WEIGHTS['is_known_brand']
    
    metadata_count = sum([
        1 for k in ['phone', 'website', 'opening_hours', 'email'] 
        if k in tags
    ])
    score += metadata_count * QUALITY_WEIGHTS['metadata_richness']
    
    return max(0, score)

def classify_poi(row):
    """
    Clasifica usando Nombre (Keywords) O Tags (OpenStreetMap).
    Retorna tupla: (Categoría, Nombre_Final)
    """
    original_name = row['name'] if pd.notnull(row['name']) else ""
    name_norm = normalize_text(original_name)
    tags = parse_all_tags(row)
    
    assigned_category = None
    
    # ESTRATEGIA 1: POR PALABRAS CLAVE
    if original_name:
        for category, config in POI_CATEGORIES.items():
            keywords = config.get("keywords", [])
            for kw in keywords:
                kw_norm = normalize_text(kw)
                pattern = rf"(?<!\w){re.escape(kw_norm)}(?!\w)"
                
                if re.search(pattern, name_norm):
                    assigned_category = category
                    break
            if assigned_category: 
                break

    # ESTRATEGIA 2: POR TAGS
    if not assigned_category:
        for category, config in POI_CATEGORIES.items():
            tag_config = config.get("tags", {})
            for tag_key, valid_values in tag_config.items():
                if tag_key in tags:
                    current_value = tags[tag_key]
                    if current_value in valid_values:
                        assigned_category = category
                        break
            if assigned_category: 
                break
    
    # VETO FINAL: EXCLUSIONES
    if assigned_category and original_name:
        exclusions = POI_CATEGORIES[assigned_category].get("exclude_keywords", [])
        if any(re.search(rf"(?<!\w){re.escape(normalize_text(ex))}(?!\w)", name_norm) for ex in exclusions):
            return None, original_name

    # RESCATE DE NOMBRE
    final_name = original_name
    smart_brand = detect_brand_smart(final_name, tags)
    
    if assigned_category and not final_name:
        if smart_brand:
            final_name = smart_brand + " (POI)"
        elif 'operator' in tags: 
            final_name = tags['operator'].title()
        else:
            final_name = f"{assigned_category} Point (System)"
            
    return assigned_category, final_name

def parse_other_tags(tags_str):
    if not tags_str or not isinstance(tags_str, str): 
        return {}
    res = {}
    try:
        parts = tags_str.split(',')
        for p in parts:
            if '=>' in p:
                k, v = p.split('=>')
                res[k.strip('" ')] = v.strip('" ')
    except: 
        pass
    return res

def process_and_upload():
    print(f"🚀 Iniciando ETL POIs - DB: {DB_NAME}")
    
    layers = ['points', 'multipolygons']
    raw_gdfs = []

    for layer in layers:
        print(f"📦 Leyendo capa: {layer}...")
        try:
            gdf = gpd.read_file(INPUT_PBF, layer=layer)
            gdf['layer'] = layer
            raw_gdfs.append(gdf)
        except Exception as e:
            print(f"⚠️  Error en capa {layer}: {e}")

    if not raw_gdfs: 
        print("❌ No se pudieron leer capas")
        return
    
    full_gdf = pd.concat(raw_gdfs, ignore_index=True)
    full_gdf = gpd.GeoDataFrame(full_gdf, geometry='geometry', crs="EPSG:4326")

    # 1. Normalizar a centroides
    print("🎯 Normalizando geometrías a centroides...")
    full_gdf['geometry'] = full_gdf['geometry'].centroid
    
    # 2. Clasificación
    print("🏷️  Clasificando POIs...")
    results = full_gdf.apply(classify_poi, axis=1)
    full_gdf['re_category'] = [res[0] for res in results]
    full_gdf['final_name'] = [res[1] for res in results]
    full_gdf['name'] = full_gdf['final_name']
    
    full_gdf = full_gdf[full_gdf['re_category'].notnull() | (full_gdf['name'] != "")].copy()
    full_gdf['re_category'] = full_gdf['re_category'].fillna('Other')
    full_gdf['name'] = full_gdf['name'].fillna('S/N')

    # 3. Unificación espacial
    print(f"📏 Unificación espacial ({SPATIAL_CONFIG['unification_radius_meters']}m)...")
    gdf_meters = full_gdf.to_crs(SPATIAL_CONFIG['crs_meters'])
    
    unified_records = []
    buffer_distance = SPATIAL_CONFIG['unification_radius_meters'] / 2
    
    for cat, group in gdf_meters.groupby('re_category'):
        print(f"   - Procesando: {cat} ({len(group)} items)")
        if len(group) == 1:
            unified_records.append(group)
            continue
            
        group_buffered = group.copy()
        group_buffered['geometry'] = group_buffered.geometry.buffer(buffer_distance)
        
        clusters = group_buffered.dissolve()
        clusters = clusters.explode(index_parts=True).reset_index()
        clusters['cluster_id'] = clusters.index
        
        group_with_clusters = gpd.sjoin(group, clusters[['cluster_id', 'geometry']], how='left', predicate='within')
        
        for cid, cluster_points in group_with_clusters.groupby('cluster_id'):
            if len(cluster_points) == 1:
                unified_records.append(cluster_points.drop(columns=['cluster_id', 'index_right'], errors='ignore'))
            else:
                best_row = cluster_points.loc[cluster_points['name'].str.len().idxmax()].copy()
                best_row['osm_id'] = cluster_points['osm_id'].dropna().iloc[0] if cluster_points['osm_id'].notna().any() else None
                unified_records.append(pd.DataFrame([best_row]))

    final_df = pd.concat(unified_records, ignore_index=True)
    final_gdf = gpd.GeoDataFrame(final_df, geometry='geometry', crs=SPATIAL_CONFIG['crs_meters']).to_crs("EPSG:4326")
    
    # 4. Preparar datos
    print(f"📤 Preparando {len(final_gdf)} registros...")
    
    upload_data = []
    for _, row in final_gdf.iterrows():
        lat, lon = row.geometry.y, row.geometry.x
        
        meta = {}
        for t in TAGS_INTERES:
            if t in row and pd.notnull(row[t]): 
                meta[t] = str(row[t])
        if 'other_tags' in row and row['other_tags']: 
            meta.update(parse_other_tags(row['other_tags']))
        
        # Aquí usamos nuestra nueva función inteligente
        brand = extract_brand(row['name'], meta)
        
        is_chain = brand is not None
        has_real_name = row['name'] != 'S/N' and row['name'] != ""
        
        quality_score = calculate_quality_score(row, row['re_category'], meta, has_real_name, brand)
        
        poi_hash = generate_poi_hash(row['name'], row['re_category'], lat, lon)
        
        osm_type = row.get('layer', 'node')
        if osm_type == 'points':
            osm_type = 'node'
        elif osm_type == 'multipolygons':
            osm_type = 'way'
        
        upload_data.append((
            int(row['osm_id']) if pd.notnull(row.get('osm_id')) else None,
            int(row['osm_way_id']) if pd.notnull(row.get('osm_way_id')) else None,
            osm_type,
            row['name'],
            brand,
            row['re_category'],
            lat,
            lon,
            f"SRID=4326;POINT({lon} {lat})",
            quality_score,
            is_chain,
            False,
            'active',
            json.dumps(meta),
            poi_hash,
            None
        ))

    # 5. Carga masiva
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    insert_query = f"""
    INSERT INTO {TABLE_NAME} 
    (osm_id, osm_way_id, osm_type, name, brand, re_category, 
     lat, lon, geometry, quality_score, is_chain, verified, status, 
     tags, hash, osm_timestamp) 
    VALUES %s 
    ON CONFLICT (hash) DO UPDATE SET 
        updated_at = CURRENT_TIMESTAMP,
        quality_score = EXCLUDED.quality_score,
        brand = EXCLUDED.brand,
        is_chain = EXCLUDED.is_chain;
    """
    
    unique_upload = {item[14]: item for item in upload_data}
    
    try:
        extras.execute_values(cur, insert_query, list(unique_upload.values()), page_size=1000)
        conn.commit()
        print(f"🎉 ¡ÉXITO! {len(unique_upload)} POIs cargados en {DB_NAME}")
        
        # Estadísticas
        cur.execute(f"SELECT re_category, COUNT(*), AVG(quality_score)::INT FROM {TABLE_NAME} GROUP BY re_category ORDER BY COUNT(*) DESC;")
        stats = cur.fetchall()
        print("\n📊 Estadísticas por categoría:")
        for cat, count, avg_score in stats:
            print(f"   {cat}: {count} POIs (Score promedio: {avg_score})")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Error DB: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    process_and_upload()
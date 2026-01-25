import os
import json
import psycopg2
import psycopg2.extras
from math import radians, sin, cos, sqrt, atan2
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv("/app/src/.env")

# --- CONFIGURACIÓN ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")
DB_NAME = os.getenv("DB_NAME", "agentic")
DB_PORT = os.getenv("DB_PORT", "5432")

CONFIG_PATH = "/app/src/ETL_POIS/cl_config_lead_prep.json"

def load_prep_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    print(f"⚠️ Warning: No config file at {CONFIG_PATH}, using defaults.")
    return {}

PREP_CONFIG = load_prep_config()

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        dbname=DB_NAME,
        port=DB_PORT
    )

def generate_lead_prep_package(property_lat, property_lon, lead_profile=None, output_file=None):
    """
    Genera el paquete de datos de preparación (Lead Prep) para una propiedad.
    Analiza Tiers críticos (Education, Health, Convenience) y Lifestyle.
    """
    print(f"🚀 Generando paquete de datos para propiedad en ({property_lat}, {property_lon})")
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    tier1_results = {}
    tier2_results = {}
    tier3_results = {}
    
    # ---------------------------------------------------------
    # 1. TIER 1: CRITICAL (Education, Health, Convenience, Safety)
    # ---------------------------------------------------------
    print("📍 Extrayendo Tier 1 POIs (Críticos)...")
    tier1_config = PREP_CONFIG.get('tier1_categories', {})
    
    for category, config in tier1_config.items():
        anchor_brands = config.get('anchor_brands', [])

        query = """
        SELECT 
            name, brand, re_category, quality_score, lat, lon, tags,
            ST_Distance(
                geometry::geography, 
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
            ) / 1000.0 as distance_km,
            -- Flag de Walkability (< threshold)
            ST_DWithin(
                geometry::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                %s
            ) as is_walkable
        FROM stage_pois_osm
        WHERE re_category = %s
          AND quality_score >= %s
          AND ST_DWithin(
                geometry::geography, 
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 
                %s
          )
        ORDER BY 
          CASE 
            WHEN brand = ANY(%s) THEN 0 
            WHEN brand = ANY(%s) THEN 1 
            ELSE 2 
          END,
          distance_km ASC,
          quality_score DESC
        LIMIT %s;
        """
        
        cur.execute(query, (
            property_lon, property_lat,  # Para distance
            property_lon, property_lat,  # Para walkable
            PREP_CONFIG['walkability_threshold_km'] * 1000,  # threshold en metros
            category,
            config['min_quality_score'],
            property_lon, property_lat,  # Para ST_DWithin
            config['radius_km'] * 1000,  # radio en metros
            anchor_brands,               # Prioridad 0 (Anchors)
            config['priority_brands'],   # Prioridad 1 (Standard Priority)
            config['limit']
        ))
        
        results = cur.fetchall()
        tier1_results[category] = [dict(row) for row in results]
        
        print(f"   ✓ {category}: {len(results)} POIs encontrados")
        
        # DEBUG LOGGING (Education & Convenience)
        if category in ["Convenience", "Education"]:
            print(f"   🐛 DEBUG {category}:")
            for r in results:
                print(f"      - {r['name']} | Dist: {r['distance_km']:.3f} km | Score: {r['quality_score']} | Brand: {r['brand']}")

    # ---------------------------------------------------------
    # 2. TIER 2: LIFESTYLE (Restaurant, Sport, Shopping)
    # ---------------------------------------------------------
    print("💎 Extrayendo Tier 2 POIs (Lifestyle)...")
    tier2_config = PREP_CONFIG.get('tier2_categories', {})
    
    for category, config in tier2_config.items():
        anchor_brands = config.get('anchor_brands', [])

        query = """
        SELECT 
            name, brand, re_category, quality_score, lat, lon, tags,
            ST_Distance(
                geometry::geography, 
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
            ) / 1000.0 as distance_km
        FROM stage_pois_osm
        WHERE re_category = %s
          AND quality_score >= %s
          AND ST_DWithin(
                geometry::geography, 
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 
                %s
          )
        ORDER BY 
          CASE 
            WHEN brand = ANY(%s) THEN 0
            WHEN brand = ANY(%s) THEN 1
            ELSE 2 
          END,
          distance_km ASC,
          quality_score DESC
        LIMIT %s;
        """
        
        cur.execute(query, (
            property_lon, property_lat,
            category,
            config['min_quality_score'],
            property_lon, property_lat,
            config['radius_km'] * 1000,
            anchor_brands,             # Prioridad 0
            config['priority_brands'], # Prioridad 1
            config['limit']
        ))
        
        results = cur.fetchall()
        tier2_results[category] = [dict(row) for row in results]
        
        print(f"   ✓ {category}: {len(results)} POIs encontrados")
        # DEBUG LIFESTYLE
        if category == "Restaurant_Cafe":
            print(f"   🐛 DEBUG {category}:")
            for r in results:
                print(f"      - {r['name']} | Dist: {r['distance_km']:.3f} km | Score: {r['quality_score']} | Brand: {r['brand']}")

    # ---------------------------------------------------------
    # 3. TIER 3: NICE TO HAVE (Nature, etc)
    # ---------------------------------------------------------
    print("🌴 Extrayendo Tier 3 POIs (Nice-to-have)...")
    tier3_config = PREP_CONFIG.get('tier3_categories', {})
    
    for category, config in tier3_config.items():
        query = """
        SELECT 
            name, brand, re_category, quality_score, lat, lon, tags,
            ST_Distance(
                geometry::geography, 
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
            ) / 1000.0 as distance_km
        FROM stage_pois_osm
        WHERE re_category = %s
          AND quality_score >= %s
          AND ST_DWithin(
                geometry::geography, 
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 
                %s
          )
        ORDER BY quality_score DESC, distance_km ASC
        LIMIT %s;
        """
        
        cur.execute(query, (
            property_lon, property_lat,
            category,
            config['min_quality_score'],
            property_lon, property_lat,
            config['radius_km'] * 1000,
            config['limit']
        ))
        
        results = cur.fetchall()
        tier3_results[category] = [dict(row) for row in results]
        print(f"   ✓ {category}: {len(results)} POIs encontrados")

    # ---------------------------------------------------------
    # 4. CALCULAR MÉTRICAS DERIVADAS
    # ---------------------------------------------------------
    print("📊 Calculando métricas...")
    
    # 4.1 Walkability Score (0-10)
    # Basado en cantidad de POIs Tier 1/2 a < 1km
    walkable_pois = 0
    for cat_list in tier1_results.values():
        walkable_pois += sum(1 for p in cat_list if p['is_walkable'])
    for cat_list in tier2_results.values():
        walkable_pois += sum(1 for p in cat_list if p['distance_km'] < PREP_CONFIG['walkability_threshold_km'])
        
    walkability_score = min(10, walkable_pois // 2) # Algoritmo simple: 2 POIs = 1 punto
    walk_label = "Walker's Paradise" if walkability_score >= 9 else \
                 "Very Walkable" if walkability_score >= 7 else \
                 "Somewhat Walkable" if walkability_score >= 4 else "Car-Dependent"

    # 4.2 Zona Premium Check
    # Reglas: AutoMercado < 3km, Starbucks < 3km, Intl School < 10km
    has_premium_grocery = False
    premium_grocery_brands = ["automercado", "freshmarket", "pricesmart"]
    
    # Buscar en Convenience si hay Grocery Premium
    for p in tier1_results.get('Convenience', []):
        brand_clean = (p['brand'] or "").replace(" ", "").lower()
        if any(b in brand_clean for b in premium_grocery_brands) and p['distance_km'] < PREP_CONFIG['premium_zone_criteria']['automercado_max_km']:
            has_premium_grocery = True
            break
            
    has_starbucks = False
    for p in tier2_results.get('Restaurant_Cafe', []):
        if 'Starbucks' in (p['brand'] or "") and p['distance_km'] < PREP_CONFIG['premium_zone_criteria']['starbucks_max_km']:
            has_starbucks = True
            break
            
    has_charging_station = False
    if tier2_results.get('Charging_Infrastructure'):
        # Si hay algun cargador en el radio configurado (5km)
        has_charging_station = True

    # Formula Flexible: (Premium Grocery) AND (School) AND (Starbucks OR Charging Station)
    # Esto permite que una zona sea premium por "lifestyle moderno" (EVs) o "lifestyle social" (Café)
    has_lifestyle_anchor = has_starbucks or has_charging_station
            
    has_intl_school = False
    for p in tier1_results.get('Education', []):
        # Asumimos que si está en la lista prioritaria de educación, es buen colegio
        if p['distance_km'] < PREP_CONFIG['premium_zone_criteria']['international_school_max_km']:
            has_intl_school = True # Simplificación: cualquier colegio top cuenta
            break
            
    is_premium_zone = has_premium_grocery and has_lifestyle_anchor and has_intl_school
    print(f"   ✓ Walkability Score: {walkability_score} ({walk_label})")
    print(f"   ✓ Premium Zone: {'SÍ' if is_premium_zone else 'NO'}")

    # ---------------------------------------------------------
    # 5. GENERAR TALKING POINTS (Argumentos de Venta)
    # ---------------------------------------------------------
    print("💬 Generando talking points...")
    talking_points = []
    
    # Hook de Colegios
    closest_school = tier1_results['Education'][0] if tier1_results.get('Education') else None
    if closest_school:
        talking_points.append(f"Perfecto para familias - {closest_school['name']} a solo {closest_school['distance_km']:.1f}km")
        
    # Hook de Walkability
    if walkability_score >= 7:
        talking_points.append(f"Estilo de vida peatonal - {walkable_pois} lugares de interés a distancia caminable")
        
    # Hook de Plusvalía (Premium)
    if is_premium_zone:
        lifestyle_hit = "Starbucks" if has_starbucks else "Puntos de Carga EV"
        if has_starbucks and has_charging_station: lifestyle_hit = "Starbucks y Carga EV"
        
        talking_points.append(f"Zona de Alta Plusvalía - Rodeado de servicios Premium (Supermercado Premium, {lifestyle_hit}, Colegios Top)")

    # ---------------------------------------------------------
    # 6. EMPAQUETAR RESULTADO
    # ---------------------------------------------------------
    package = {
        "property_location": {"lat": property_lat, "lon": property_lon},
        "metrics": {
            "walkability_score": walkability_score,
            "walkability_label": walk_label,
            "is_premium_zone": is_premium_zone,
            "total_pois_analyzed": walkable_pois  # approx
        },
        "tier_1_critical_pois": tier1_results,
        "tier_2_lifestyle_pois": tier2_results,
        "tier_3_nice_to_have_pois": tier3_results,
        "talking_points": {
            "opening_hooks": talking_points,
            "objection_handlers": [] # TODO: Generar handlers
        }
    }
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(package, f, indent=4, ensure_ascii=False)
        print(f"💾 Paquete guardado en: {output_file}")
            
    cur.close()
    conn.close()
    
    return package

def print_summary(package):
    """Imprime un resumen bonito en consola para el desarrollador."""
    print("\n" + "="*60)
    print("📋 RESUMEN DEL PAQUETE DE LEAD PREP")
    print("="*60)
    
    print(f"\n🎯 MÉTRICAS CLAVE:")
    print(f"   Walkability: {package['metrics']['walkability_score']} ({package['metrics']['walkability_label']})")
    print(f"   Zona Premium: {'✅ SÍ' if package['metrics']['is_premium_zone'] else '❌ NO'}")
    print(f"   Total POIs: {package['metrics']['total_pois_analyzed']}") # placeholder
    
    print(f"\n📍 TIER 1 (Críticos):")
    for cat, pois in package['tier_1_critical_pois'].items():
        print(f"   {cat}: {len(pois)} POIs")
        if pois:
            best = pois[0]
            print(f"      → Mejor: {best['name']} ({best['distance_km']:.1f}km)")
    
    print(f"\n💎 TIER 2 (Lifestyle):")
    for cat, pois in package['tier_2_lifestyle_pois'].items():
        print(f"   {cat}: {len(pois)} POIs")
        if pois:
            best = pois[0]
            print(f"      → Mejor: {best['name']} ({best['distance_km']:.1f}km)")
    
    print(f"\n💬 TALKING POINTS:")
    for hook in package['talking_points']['opening_hooks']:
        print(f"   • {hook}")
    
    print("\n" + "="*60)

def save_geojson(package, output_path):
    """Convierte el paquete Lead Prep a GeoJSON para visualización."""
    features = []
    
    # 1. Feature de la Propiedad (TARGET)
    prop_data = package['property_location']
    features.append({
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [prop_data['lon'], prop_data['lat']]
        },
        "properties": {
            "name": "PROPIEDAD OBJETIVO",
            "type": "TARGET",
            "marker-color": "#ff0000",
            "marker-size": "large",
            "marker-symbol": "star"
        }
    })
    
    # 2. Features de los POIs
    colors = {
        "Education": "#0000ff",      # Azul
        "Health": "#ff00ff",         # Magenta
        "Convenience": "#00ff00",    # Verde
        "Safety": "#555555",         # Gris
        "Restaurant_Cafe": "#ffa500",# Naranja
        "Shopping": "#800080",       # Morado
        "Sport_Leisure": "#008080",  # Teal
        "Charging_Infrastructure": "#00c4de", # Cyan Electrico
        "Nature_Tourism": "#228b22"  # Forest Green
    }
    
    # Recorrer Tier 1 y Tier 2
    all_categories = {**package['tier_1_critical_pois'], **package['tier_2_lifestyle_pois'], **package.get('tier_3_nice_to_have_pois', {})}
    
    for cat, pois in all_categories.items():
        color = colors.get(cat, "#7e7e7e")
        for poi in pois:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [poi['lon'], poi['lat']]
                },
                "properties": {
                    "name": poi['name'],
                    "brand": poi['brand'],
                    "category": cat,
                    "distance_km": f"{poi['distance_km']:.2f} km",
                    "score": poi['quality_score'],
                    "marker-color": color,
                    "marker-symbol": "circle"
                }
            })
            
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)
        
    print(f"🗺️  GeoJSON guardado en: {output_path}")

if __name__ == "__main__":
    # --- EJEMPLO DE USO ---
    
    # Ejemplo 2: Propiedad en Granadilla (Usuario - Exacta)
    PROPERTY_LAT = 9.910243
    PROPERTY_LON = -84.026490
    
    # Perfil del lead (opcional)
    LEAD_PROFILE = {
        "family_status": "school_age_kids",
        "work_style": "hybrid",
        "fitness_oriented": True,
        "needs_international_school": True
    }
    
    # Generar paquete
    package = generate_lead_prep_package(
        property_lat=PROPERTY_LAT,
        property_lon=PROPERTY_LON,
        lead_profile=LEAD_PROFILE,
        output_file="/app/src/ETL_POIS/lead_prep_package_result.json"
    )
    
    # Imprimir resumen
    print_summary(package)
    
    # Guardar GeoJSON para mapa visual
    save_geojson(package, "/app/src/ETL_POIS/mapa_propiedad.geojson")
    
    print(f"\n✨ Para usar desde código:")
    print(f"   from lead_prep_generator import generate_lead_prep_package")
    print(f"   package = generate_lead_prep_package(lat, lon, lead_profile)")
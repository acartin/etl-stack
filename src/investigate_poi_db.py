
import os
import json
from uuid import UUID
from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

load_dotenv()

# DB Config
DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
engine = create_engine(DB_URL)

print("--- Table Inspection: stage_pois_osm ---")
insp = inspect(engine)
columns = [c['name'] for c in insp.get_columns('stage_pois_osm')]
print(f"Columns: {columns}")

PROP_UUID = '685a1950-8f0e-4e86-929a-9e12148057a3'

print(f"--- Investigating Property {PROP_UUID} ---")

with engine.connect() as conn:
    # 1. Get Property Details
    sql_prop = text("""
        SELECT id, external_prop_id, location_lat, location_lng, address_street, poi_data, created_at 
        FROM lead_properties 
        WHERE id = :uuid
    """)
    prop = conn.execute(sql_prop, {"uuid": PROP_UUID}).fetchone()
    
    if not prop:
        print("❌ Property NOT FOUND in DB.")
        exit()

    lat = float(prop.location_lat) if prop.location_lat else None
    lon = float(prop.location_lng) if prop.location_lng else None
    prop_poi_data = prop.poi_data

    print(f"✅ Property Found: ExtID={prop.external_prop_id}")
    print(f"   Created At: {prop.created_at}") # Check timestamp
    print(f"   Coords: ({lat}, {lon})")
    print(f"   Address: {prop.address_street}")
    print(f"   POI Data: {prop_poi_data}")
    
    if lat is None or lon is None:
        print("❌ Coordinates are NULL. POI matching impossible.")
        exit()

    # 3. Check Nearby OSM POIs (Simple Box Search ~1km approx)
    delta = 0.005 # ~500m radius approx for quick check
    min_lat, max_lat = lat - delta, lat + delta
    min_lon, max_lon = lon - delta, lon + delta

    sql_osm = text("""
        SELECT count(*), re_category, name, quality_score 
        FROM stage_pois_osm 
        WHERE CAST(lat AS FLOAT) BETWEEN :min_lat AND :max_lat
          AND CAST(lon AS FLOAT) BETWEEN :min_lon AND :max_lon
        GROUP BY re_category, name, quality_score
    """)
    
    raw_osm_pois = conn.execute(sql_osm, {
        "min_lat": min_lat, "max_lat": max_lat,
        "min_lon": min_lon, "max_lon": max_lon
    }).fetchall()

    print(f"\n--- Nearby OSM POIs (+/- 0.005 deg) ---")
    total_nearby = 0
    for p in raw_osm_pois:
        print(f"   Found {p[0]} of cat '{p[1]}' ({p[2]}) Score={p[3]}")
        total_nearby += p[0]
    
    print(f"   Total Nearby Raw Candidates: {total_nearby}")

    print("\n" + "="*30)
    if prop_poi_data and prop_poi_data != "null":
        print(f"✅ FINAL VERIFICATION: POI Data Matches Found! (Type: {type(prop_poi_data)})")
        print("Note: If 'prop_poi_data' is a dict/list, it is populated.")
    else:
        print("❌ FINAL VERIFICATION: POI Data is still None/Empty.")
    print("="*30)

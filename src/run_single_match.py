
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv
import sys

# Setup Path
sys.path.append("/app/src")
load_dotenv("/app/src/.env")

from ETL_POIS.cl_test1 import generate_lead_prep_package
from ETL_POIS.properties_poi_matcher import transform_package_to_frontend_json, get_db_connection

PROP_UUID = '685a1950-8f0e-4e86-929a-9e12148057a3'

def run():
    print(f"🚀 Running Single Match for {PROP_UUID}")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Get Property
            cur.execute("SELECT id, title, location_lat, location_lng FROM lead_properties WHERE id = %s", (PROP_UUID,))
            p = cur.fetchone()
            
            if not p:
                print("❌ Property not found")
                return

            print(f"📍 Property: {p['title']} ({p['location_lat']}, {p['location_lng']})")

            # 2. Generate Package
            full_package = generate_lead_prep_package(
                property_lat=float(p['location_lat']),
                property_lon=float(p['location_lng']),
                output_file=None
            )
            
            # 3. Transform
            frontend_json = transform_package_to_frontend_json(full_package)
            print(f"📦 JSON Generated. POI Count: {len(frontend_json.get('map_points', []))}")

            # 4. Update DB
            cur.execute("""
                UPDATE public.lead_properties
                SET poi_data = %s
                WHERE id = %s
            """, (Json(frontend_json), p['id']))
            
            conn.commit()
            print("💾 DB Update Committed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run()

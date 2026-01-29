import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from providers.realhomes_provider import RealHomesProvider
from providers.houzez_provider import HouzezProvider
from providers.wp_residence_provider import WPResidenceProvider

# Mapeo de strings de la BD a Clases de Python
PROVIDER_MAP = {
    "realhomes": RealHomesProvider,
    "houzez": HouzezProvider,
    "wp_residence": WPResidenceProvider
}

def get_db_connection():
    load_dotenv()
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )

import sys

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ETL Properties Ingestor")
    parser.add_argument("site_name", nargs="?", help="Nombre del sitio (debe coincidir con la DB)")
    parser.add_argument("--force", action="store_true", help="Forzar re-extracción total ignorando fechas")
    parser.add_argument("--limit", type=int, default=None, help="Limitar cantidad de propiedades (para pruebas)")
    args = parser.parse_args()

    target_site = args.site_name
    force_reextract = args.force
    limit = args.limit
    
    if force_reextract:
        print("⚡ Modo FORCE activado: se re-extraerán TODAS las propiedades.")
    if limit:
        print(f"🛑 Límite de prueba activado: {limit} propiedades.")
    
    run_ingest(target_site, force_reextract, limit)

def run_ingest(target_site, force_reextract=False, limit=None):
    """
    Orquesta la ingesta para un sitio específico
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT client_id, name, provider_type, base_url, api_endpoint 
        FROM public.stage_sources_config 
        WHERE is_active = true
    """
    params = []
    
    if target_site:
        query += " AND name = %s"
        params.append(target_site)
        print(f"🔍 Filtrando ingesta para sitio: {target_site}")
    
    print("🔍 Consultando configuraciones en public.stage_sources_config...")
    
    try:
        cur.execute(query, params)
        targets = cur.fetchall()
        
        if not targets:
            print("⚠️ No hay fuentes activas para procesar.")
            return

        for target in targets:
            print(f"\n🌟 INICIANDO INGESTA PARA: {target['name']}")
            
            # --- NUEVO: Obtener IDs y Fechas de actualización existentes ---
            cur.execute(
                "SELECT external_prop_id, updated_at FROM public.lead_properties WHERE client_id = %s",
                (target['client_id'],)
            )
            # Creamos un diccionario {id: fecha}
            known_data = {row['external_prop_id']: row['updated_at'] for row in cur.fetchall()}
            print(f"📡 Se encontraron {len(known_data)} propiedades registradas.")

            # 1. Obtener la clase del provider
            provider_class = PROVIDER_MAP.get(target['provider_type'])
            if not provider_class:
                print(f"❌ Provider '{target['provider_type']}' no implementado. Saltando...")
                continue
            
            # 2. Instanciar el provider con datos de la DB
            provider = provider_class(
                site_name=target['name'],
                base_url=target['base_url'],
                api_endpoint=target['api_endpoint']
            )
            
            # 2.1 Intentar cargar datos previos para reanudación (si no es modo force)
            output_path = f"/app/src/ETL_PROPERTIES/output/{target['name'].replace(' ', '_')}.json"
            if not force_reextract:
                provider.load_existing_data(output_path)
            
            # 3. Ejecutar extracción inteligente
            # En modo force, pasamos known_data vacío para forzar re-extracción
            provider.run_full_extraction(
                limit=limit, 
                output_path=output_path, 
                client_id=target['client_id'],
                known_data={} if force_reextract else known_data
            )
            
            # 4. Guardar JSON normalizado (final)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            provider.save_to_json(output_path, client_id=target['client_id'])
            
            # 5. Actualizar última ejecución en la DB
            cur.execute(
                "UPDATE public.stage_sources_config SET last_run_at = now() WHERE name = %s",
                (target['name'],)
            )
            conn.commit()

    except Exception as e:
        print(f"❌ Error general en la ingesta: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging
from providers import get_image_provider

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageLoader:
    def __init__(self):
        load_dotenv("/app/src/.env")
        self.conn = self.get_db_connection()
        self.provider_mappings = self.get_provider_mappings()

    def get_db_connection(self):
        return psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            cursor_factory=RealDictCursor
        )

    def get_provider_mappings(self):
        """Obtiene la relación client_id -> provider_type de la DB."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT client_id, provider_type FROM public.stage_sources_config")
            rows = cur.fetchall()
            return {str(row['client_id']): row['provider_type'] for row in rows}

    def get_real_property_id(self, client_id, external_id):
        """Mapea el external_id del JSON al UUID real de lead_properties."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM public.lead_properties WHERE client_id = %s AND external_prop_id = %s",
                (client_id, str(external_id))
            )
            row = cur.fetchone()
            return row['id'] if row else None

    def save_image_to_db(self, property_id, original_url, local_path, content_hash, sort_order, is_main):
        """Registra o actualiza la imagen en lead_property_images."""
        with self.conn.cursor() as cur:
            # Primero verificamos si ya existe para evitar duplicados sin depender de constraints únicos
            cur.execute(
                "SELECT id FROM public.lead_property_images WHERE property_id = %s AND (content_hash = %s OR original_url = %s)",
                (property_id, content_hash, original_url)
            )
            row = cur.fetchone()
            
            if row:
                cur.execute("""
                    UPDATE public.lead_property_images SET
                        local_path = %s,
                        is_main = %s,
                        sort_order = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (local_path, is_main, sort_order, row['id']))
            else:
                cur.execute("""
                    INSERT INTO public.lead_property_images 
                    (property_id, original_url, local_path, content_hash, sort_order, is_main)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (property_id, original_url, local_path, content_hash, sort_order, is_main))
            
            self.conn.commit()

    def process_json_file(self, filepath, max_properties=20):
        """Procesa TODAS las imágenes de las primeras 'max_properties' propiedades."""
        logger.info(f"📂 Iniciando procesamiento de muestra para: {os.path.basename(filepath)}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        client_id_str = str(data.get("metadata", {}).get("client_id", ""))
        provider_type = self.provider_mappings.get(client_id_str)
        
        if not provider_type:
            logger.warning(f"⚠️ No hay provider_type definido para el cliente {client_id_str}")
            return

        image_provider = get_image_provider(provider_type)
        if not image_provider:
            logger.error(f"❌ No se encontró clase provider para tipo: {provider_type}")
            return

        properties_processed_count = 0
        total_images_downloaded = 0
        properties = data.get("properties", [])

        for prop in properties:
            if properties_processed_count >= max_properties:
                break

            external_id = prop.get("external_id")
            real_prop_id = self.get_real_property_id(client_id_str, external_id)

            if not real_prop_id:
                # logger.warning(f"⏩ Propiedad {external_id} no encontrada en lead_properties. Saltando...")
                continue
            
            # --- Procesando Propiedad ---
            properties_processed_count += 1
            
            # El provider sabe dónde buscar en el snapshot o en el objeto normalizado
            urls = image_provider.get_image_urls(prop)
            
            if not urls:
                logger.info(f"ℹ️  Propiedad {external_id} sin imágenes. ({properties_processed_count}/{max_properties})")
                continue

            logger.info(f"🏠 Procesando Propiedad {properties_processed_count}/{max_properties} ({external_id}) - {len(urls)} imágenes encontradas.")

            for i, url in enumerate(urls):
                # 1. Descargar (Staging)
                download_info = image_provider.download_image(url, client_id_str, real_prop_id)
                if not download_info:
                    continue

                # 2. Procesar y Guardar (Storage)
                # Esto mueve de staging a storage jerárquico
                local_rel_path = image_provider.process_and_store(download_info, client_id_str, real_prop_id)
                
                if local_rel_path:
                    # 3. Registrar en DB
                    is_main = (i == 0)
                    self.save_image_to_db(
                        real_prop_id, 
                        url, 
                        local_rel_path, 
                        download_info["content_hash"], 
                        i, 
                        is_main
                    )
                    total_images_downloaded += 1
                    # logger.info(f"✨ IMG OK: {os.path.basename(local_rel_path)}")

        logger.info(f"✅ Finalizado: {total_images_downloaded} imágenes procesadas de {properties_processed_count} propiedades para {os.path.basename(filepath)}")

if __name__ == "__main__":
    loader = ImageLoader()
    output_dir = "/app/src/ETL_PROPERTIES/output"
    
    # Procesar cada JSON disponible en el output de propiedades
    for filename in os.listdir(output_dir):
        if filename.endswith(".json"):
            loader.process_json_file(os.path.join(output_dir, filename), max_properties=20)

import os
import shutil
import psycopg2
from dotenv import load_dotenv
import logging
import argparse

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageGarbageCollector:
    def __init__(self):
        load_dotenv("/app/src/.env")
        self.storage_root = "/app/data/storage/images"
        self.conn = self.get_db_connection()

    def get_db_connection(self):
        return psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS")
        )

    def get_active_properties(self, client_id=None):
        """Retorna un set de property_ids (UUID strings) que existen en la BD."""
        query = "SELECT id FROM public.lead_properties"
        params = []
        
        if client_id:
            query += " WHERE client_id = %s"
            params.append(client_id)
            
        with self.conn.cursor() as cur:
            cur.execute(query, tuple(params))
            return {str(row[0]) for row in cur.fetchall()}

    def get_active_images(self, property_id):
        """Retorna un set de hashes (nombres de archivo sin extensión) válidos para una propiedad."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT content_hash FROM public.lead_property_images WHERE property_id = %s", (property_id,))
            return {row[0] for row in cur.fetchall()}

    def prune_storage(self, target_client_id=None):
        """
        Recorre el disco y borra:
        1. Carpetas de propiedades que NO están en la DB (Nivel Propiedad).
        2. Archivos de imágenes que NO están en la DB (Nivel Archivo).
        """
        if not os.path.exists(self.storage_root):
            logger.warning(f"⚠️ El directorio {self.storage_root} no existe.")
            return

        # Obtenemos TODOS los IDs válidos de la DB (Verdad absoluta)
        logger.info("🔍 Consultando base de datos para obtener propiedades activas...")
        active_prop_ids = self.get_active_properties(target_client_id)
        logger.info(f"✅ Se encontraron {len(active_prop_ids)} propiedades activas en DB.")

        # Recorremos el filesystem
        clients_dirs = [d for d in os.listdir(self.storage_root) if os.path.isdir(os.path.join(self.storage_root, d))]
        
        cleaned_folders = 0
        cleaned_files = 0
        reclaimed_bytes = 0

        for client_uuid in clients_dirs:
            if target_client_id and client_uuid != str(target_client_id):
                continue
            
            # Ajuste crítico: Entrar a la subcarpeta 'properties'
            client_properties_path = os.path.join(self.storage_root, client_uuid, "properties")
            
            if not os.path.exists(client_properties_path):
                # Si no tiene carpeta de propiedades, ignoramos (puede ser solo branding)
                continue

            properties_dirs = [d for d in os.listdir(client_properties_path) if os.path.isdir(os.path.join(client_properties_path, d))]

            for prop_uuid in properties_dirs:
                prop_path = os.path.join(client_properties_path, prop_uuid)
                
                # NIVEL 1: Limpieza de Propiedad Completa
                if prop_uuid not in active_prop_ids:
                    try:
                        size = sum(os.path.getsize(os.path.join(dirpath, filename)) 
                                   for dirpath, _, filenames in os.walk(prop_path) 
                                   for filename in filenames)
                        shutil.rmtree(prop_path)
                        logger.info(f"🗑️  [PROPIEDAD] Eliminado huérfano: {prop_uuid} ({size/1024:.2f} KB)")
                        cleaned_folders += 1
                        reclaimed_bytes += size
                    except Exception as e:
                        logger.error(f"❌ Error borrando propiedad {prop_path}: {e}")
                    continue # Si borramos la carpeta, no hace falta revisar archivos

                # NIVEL 2: Limpieza Profunda de Archivos
                # Si la propiedad es válida, verificamos sus archivos internos
                try:
                    valid_hashes = self.get_active_images(prop_uuid)
                    files = [f for f in os.listdir(prop_path) if f.endswith(".webp")]
                    
                    for filename in files:
                        content_hash = os.path.splitext(filename)[0]
                        if content_hash not in valid_hashes:
                            file_path = os.path.join(prop_path, filename)
                            size = os.path.getsize(file_path)
                            os.remove(file_path)
                            logger.info(f"📄 [ARCHIVO] Eliminado huérfano: {filename} en {prop_uuid} ({size/1024:.2f} KB)")
                            cleaned_files += 1
                            reclaimed_bytes += size
                except Exception as e:
                    logger.error(f"⚠️ Error verificando archivos en {prop_uuid}: {e}")

        # PASO FINAL: Eliminar carpetas que quedaron vacías
        self.remove_empty_folders()

        logger.info(f"✨ Limpieza finalizada.")
        logger.info(f"   - Carpetas de Propiedades eliminadas: {cleaned_folders}")
        logger.info(f"   - Archivos de Imágenes eliminados:  {cleaned_files}")
        logger.info(f"   - Espacio total recuperado: {reclaimed_bytes / (1024*1024):.2f} MB")

    def remove_empty_folders(self):
        """Recorre de abajo hacia arriba y elimina carpetas vacías."""
        logger.info("🧹 Buscando y eliminando carpetas vacías...")
        removed_count = 0
        for dirpath, _, _ in os.walk(self.storage_root, topdown=False):
            if dirpath == self.storage_root:
                continue # No borrar la raíz storage/images
            try:
                # Intentamos borrar siempre. os.rmdir falla si no está vacío (OSError [Errno 39])
                # Esto soluciona el problema de que 'dirnames' no se actualiza al borrar hijos.
                os.rmdir(dirpath)
                removed_count += 1
            except OSError:
                pass # No estaba vacía, seguimos
        
        if removed_count > 0:
            logger.info(f"🗑️  Se eliminaron {removed_count} carpetas vacías.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Elimina imágenes físicas de propiedades que ya no existen en DB.")
    parser.add_argument("--client_id", type=str, help="Limitar limpieza a un cliente específico (UUID)")
    
    args = parser.parse_args()
    
    gc = ImageGarbageCollector()
    gc.prune_storage(args.client_id)

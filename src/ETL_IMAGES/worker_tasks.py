
import os
import sys
import logging
import traceback
from uuid import UUID

# Configurar sys.path para que los imports funcionen
sys.path.append("/app/src")

from src.ETL_IMAGES.image_loader import ImageLoader
from src.ETL_IMAGES.image_ai_tagger import ImageAITagger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - WORKER_TASK - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def restore_images_task(site_name: str, limit: int = None):
    """
    Tarea para restaurar imágenes de un sitio específico.
    """
    logger.info(f"🚀 [TASK] Iniciando restauración de imágenes para: {site_name}")
    try:
        loader = ImageLoader()
        output_dir = "/app/src/ETL_PROPERTIES/output"
        filename = f"{site_name.replace(' ', '_')}.json"
        filepath = os.path.join(output_dir, filename)
        
        if not os.path.exists(filepath):
            logger.error(f"❌ [TASK] No se encontró el archivo JSON para el sitio: {site_name}")
            return {"status": "FAILED", "error": f"JSON not found for {site_name}"}
            
        # Correr el proceso de carga
        # Nota: image_loader.process_json_file usa 'max_properties'
        loader.process_json_file(filepath, max_properties=limit or 999999)
        
        logger.info(f"✅ [TASK] Restauración completada para: {site_name}")
        return {"status": "SUCCESS", "site": site_name}
        
    except Exception as e:
        logger.error(f"❌ [TASK] Error en restauración de {site_name}: {e}")
        logger.error(traceback.format_exc())
        return {"status": "FAILED", "error": str(e)}

def run_tagging_task(site_name: str, limit: int = 50):
    """
    Tarea para correr el etiquetado AI de un sitio.
    """
    logger.info(f"🚀 [TASK] Iniciando Etiquetado AI para: {site_name} (Límite: {limit})")
    try:
        tagger = ImageAITagger()
        # run_full_process(batch_size=10, max_total_images=50, client_name=None)
        tagger.run_full_process(max_total_images=limit, client_name=site_name)
        
        logger.info(f"✅ [TASK] Etiquetado completado para: {site_name}")
        return {"status": "SUCCESS", "site": site_name}
        
    except Exception as e:
        logger.error(f"❌ [TASK] Error en etiquetado de {site_name}: {e}")
        logger.error(traceback.format_exc())
        return {"status": "FAILED", "error": str(e)}

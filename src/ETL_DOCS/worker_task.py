
import logging
from uuid import UUID
from src.ETL_DOCS.processor import DocumentProcessor

# Configuración de log dedicada al Worker
logger = logging.getLogger("worker")

def process_document_task(file_path: str, client_id: UUID, content_id: str, original_filename: str):
    """
    Tarea ejecutable por RQ Worker.
    Es un wrapper simple alrededor del Processor, pero esencial para que RQ pueda
    serializar la llamada (pickle).
    """
    logger.info(f"👷 [WORKER] Iniciando tarea para: {content_id}")
    try:
        # Instanciar procesador fresco para cada tarea (Thread-safe)
        processor = DocumentProcessor()
        
        result = processor.process_document(
            file_path=file_path,
            client_id=client_id,
            content_id=content_id,
            original_filename=original_filename
        )
        
        logger.info(f"✅ [WORKER] Tarea completada: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ [WORKER] Tarea fallida para {content_id}: {e}")
        # Re-lanzar para que RQ marque el job como Failed
        raise e

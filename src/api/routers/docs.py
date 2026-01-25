
import os
import shutil
import logging
from uuid import UUID, uuid4
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
# Eliminamos BackgroundTasks, importamos Redis y RQ
from redis import Redis
from rq import Queue

from src.shared.file_manager import FileManager
from src.shared.vector_store import VectorStore
# Importamos la tarea, no el procesador directo
from src.ETL_DOCS.worker_task import process_document_task

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["Start/Documents"]
)

# --- CONFIGURACIÓN REDIS ---
# Conectamos a localhost porque estamos en el mismo contenedor
redis_conn = Redis(host='localhost', port=6379, db=0)
q = Queue('etl_queue', connection=redis_conn)

# VectorStore para deletes directos (síncronos)
vector_store = VectorStore() 

@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    client_id: UUID = Form(...),
    content_id: Optional[str] = Form(None)
):
    """
    Subida de documentos PDF v2 (Redis Queue).
    
    1. Guarda en disco.
    2. Encola tarea en Redis ('etl_queue').
    3. Retorna Job ID para tracking.
    """
    try:
        # 1. Validaciones
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF.")
        
        final_content_id = content_id or f"doc_{uuid4()}"
        file_bytes = await file.read()
        
        # 2. Guardado Seguro en Disco
        try:
            saved_path = FileManager.save_upload(file_bytes, file.filename, client_id)
        except IOError as e:
            raise HTTPException(status_code=500, detail=f"Error I/O: {str(e)}")

        # 3. Encolar en Redis (Escalabilidad Real)
        # job_timeout=600 (10 minutos para PDFs grandes/OCR)
        job = q.enqueue(
            process_document_task,
            args=(saved_path, client_id, final_content_id, file.filename),
            job_timeout=600,
            result_ttl=86400, # Guardar resultado 24h
            job_id=f"job_{final_content_id}" # ID determinista para tracking fácil
        )

        return {
            "status": "QUEUED",
            "message": "Documento encolado para procesamiento.",
            "job_id": job.get_id(),
            "content_id": final_content_id,
            "filename": file.filename,
            "queue_position": len(q) # Info útil para el usuario
        }

    except Exception as e:
        logger.error(f"Error en upload endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    """Consultar estado del procesamiento"""
    try:
        job = q.fetch_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        
        return {
            "job_id": job.get_id(),
            "status": job.get_status(), # queued, started, finished, failed
            "result": job.result,
            "enqueued_at": job.enqueued_at,
            "error": job.exc_info # Si falló, aquí sale el traceback
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{client_id}/{content_id}")
def delete_document(client_id: UUID, content_id: str):
    """Borrado síncrono (Granular)"""
    try:
        vector_store.delete_document(client_id, content_id)
        # TODO: Borrar archivo físico también (usando FileManager)
        return {"status": "DELETED", "content_id": content_id}
    except Exception as e:
        logger.error(f"Error delete doc: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/client/{client_id}")
def delete_client_resources(client_id: UUID):
    """Borrado síncrono (Cliente Completo)"""
    try:
        vector_store.delete_client(client_id)
        FileManager.delete_client_folder(client_id)
        return {"status": "CLIENT_PURGED", "client_id": str(client_id)}
    except Exception as e:
        logger.error(f"Error purga client: {e}")
        raise HTTPException(status_code=500, detail=str(e))

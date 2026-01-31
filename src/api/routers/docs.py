
import os
import shutil
import logging
from uuid import UUID, uuid4
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
import psycopg2 
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
    content_id: Optional[str] = Form(None),
    visibility: str = Form("private"),
    access_level: Optional[str] = Form(None), # Alias para visibility
    category: str = Form("knowledge_base")
):
    """
    Subida de documentos PDF v2 (Redis Queue).
    
    1. Guarda en disco.
    2. Encola tarea en Redis ('etl_queue').
    3. Retorna Job ID para tracking.
    """
    try:
        # Resolver Visibilidad (access_level > visibility)
        final_visibility = access_level if access_level else visibility

        # 1. Validaciones
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF.")
        
        final_content_id = content_id or f"doc_{uuid4()}"
        
        # 1.5. Sanitización básica
        filename = os.path.basename(file.filename) # Evitar path traversal

        # 2. Validación de Duplicados Físicos (Prevención de Orphans) - CHECK DIRECTO
        if FileManager.check_file_exists(client_id, filename):
            raise HTTPException(
                status_code=409, 
                detail=f"El archivo '{filename}' ya existe físicamente. Renómbrelo o borre el anterior."
            )

        file_bytes = await file.read()
        
        # 2. Guardado Seguro en Disco
        try:
            saved_path = FileManager.save_upload(file_bytes, file.filename, client_id)
        except IOError as e:
            raise HTTPException(status_code=500, detail=f"Error I/O: {str(e)}")

        # 3. Registrar en Registro Maestro (ai_knowledge_documents)
        try:
            vector_store.register_document_in_db(
                client_id=client_id, 
                filename=filename, 
                storage_path=saved_path, 
                content_id=final_content_id, 
                access_level=final_visibility,
                category=category
            )
        except psycopg2.errors.UniqueViolation:
            # Captura explícita de error de integridad (Duplicado en DB)
            try:
                os.remove(saved_path) # Rollback físico
            except:
                pass
            raise HTTPException(status_code=409, detail="El documento ya está registrado en la base de datos (Duplicado).")

        except HTTPException:
            # Re-lanzar excepciones HTTP conocidas (como el 409 de archivo físico)
            raise
            
        except Exception as e:
            # Captura secundaria por si falla el string check antiguo o es otro error
            logger.error(f"Error registrando en DB: {e}")
            raise HTTPException(status_code=500, detail=f"Error al registrar documento en la base de datos: {e}")

        # 4. Encolar en Redis (Escalabilidad Real)
        # job_timeout=600 (10 minutos para PDFs grandes/OCR)
        job = q.enqueue(
            process_document_task,
            args=(saved_path, client_id, final_content_id, file.filename, final_visibility, category),
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

    except HTTPException:
        # Re-lanzar excepciones HTTP intencionadas (400, 409, etc.)
        raise
    
    except Exception as e:
        logger.error(f"Error en upload endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list/{client_id}")
def get_client_documents(client_id: UUID):
    """Listar documentos registrados para un cliente (Grid UI)"""
    try:
        docs = vector_store.list_documents(client_id)
        return {
            "status": "success",
            "client_id": client_id,
            "count": len(docs),
            "documents": docs
        }
    except Exception as e:
        logger.error(f"Error listando documentos: {e}")
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
    """Borrado síncrono (Granular, incluyendo archivo físico)"""
    try:
        # 1. Borrar de BD y obtener nombre del archivo
        filename = vector_store.delete_document(client_id, content_id)
        
        # 2. Borrar archivo físico si se encontró el registro
        if filename:
            FileManager.delete_document(client_id, filename)
            return {"status": "DELETED", "content_id": content_id, "file_purged": True}
        
        return {"status": "DELETED_DB_ONLY", "content_id": content_id, "file_purged": False}
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

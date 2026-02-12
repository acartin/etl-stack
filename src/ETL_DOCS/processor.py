
import logging
import os
import io
import hashlib
from uuid import UUID
from typing import Optional, Dict, Any

import pypdf
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

from src.shared.schemas import CanonicalDocument, SourceType, IngestStatus
from src.shared.vector_store import VectorStore
from src.shared.file_manager import FileManager

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """
    Orquestador del ETL de Documentos.
    Responsabilidades:
    1. Recibir path de archivo físico.
    2. Extraer texto (pypdf o OCR fallback).
    3. Construir CanonicalDocument.
    4. Delegar persistencia a VectorStore.
    """

    def __init__(self):
        self.vector_store = VectorStore()
        
    def _extract_text_from_pdf(self, file_path: str) -> str:
        """
        Intenta extracción rápida con pypdf. 
        Si retorna poco texto, asume imagen escaneada y usa OCR.
        """
        text = ""
        try:
            # 1. Intento Rápido (Texto seleccionable)
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            # Limpieza básica
            text = text.strip()

            # 2. Check de Calidad / OCR Fallback
            # Si hay muy poco texto (< 50 chars) para un PDF, probablemente sea imagen
            if len(text) < 50:
                logger.info(f"Texto insuficiente detectado ({len(text)} chars). Iniciando OCR para {file_path}...")
                text = self._ocr_pdf(file_path)
            
            return text

        except Exception as e:
            logger.error(f"Error parseando PDF {file_path}: {e}")
            raise ValueError(f"No se pudo leer el PDF: {e}")

    def _ocr_pdf(self, file_path: str) -> str:
        """Usa pdf2image + pytesseract para documentos escaneados"""
        text = ""
        try:
            # Convertir PDF a imágenes (una por página)
            images = convert_from_path(file_path)
            for i, image in enumerate(images):
                # Tesseract OCR
                page_text = pytesseract.image_to_string(image, lang='spa') # Prioridad Español
                text += page_text + "\n"
                logger.debug(f"OCR Página {i+1} completado")
            return text.strip()
        except Exception as e:
            logger.error(f"Fallo crítico en OCR: {e}")
            raise

    def process_document(self, 
                         file_path: str, 
                         client_id: UUID, 
                         content_id: str,
                         original_filename: str,
                         source: SourceType = SourceType.PDF_UPLOAD,
                         access_level: str = "private",
                         category: str = "knowledge_base") -> Dict[str, Any]:
        """
        Flujo principal de procesamiento con fragmentación por páginas.
        """
        logger.info(f"Iniciando procesamiento ETL para: {original_filename} ({content_id})")

        try:
            # 1. Extracción de Texto por páginas
            logger.info(f"Pasando a extracción de texto para {file_path}")
            reader = pypdf.PdfReader(file_path)
            pages_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and len(text.strip()) > 10:
                    pages_text.append({
                        "text": text.strip(),
                        "page_number": i + 1
                    })
            
            logger.info(f"Texto extraído: {len(pages_text)} páginas con contenido.")

            # OCR Fallback si no hay texto extraído
            if not pages_text:
                logger.info(f"No se detectó texto seleccionable. Iniciando OCR para {file_path}...")
                full_ocr_text = self._ocr_pdf(file_path)
                pages_text.append({"text": full_ocr_text, "page_number": 1})

            if not pages_text:
                raise ValueError("El documento está vacío o no se pudo extraer texto legible.")

            # 2. Limpieza de fragmentos previos
            logger.info(f"Limpiando fragmentos previos para {content_id}")
            with self.vector_store.conn.cursor() as cur:
                cur.execute("DELETE FROM ai_vectors WHERE client_id = %s AND (content_id = %s OR content_id LIKE %s)", 
                            (str(client_id), content_id, f"{content_id}_part_%"))

            # 3. Procesamiento y Carga de Fragmentos
            total_chars = 0
            from src.shared.schemas import CanonicalMetadata
            
            for item in pages_text:
                chunk_id = f"{content_id}_part_{item['page_number']}"
                logger.info(f"Procesando fragmento: {chunk_id}")
                chunk_hash = self.vector_store.calculate_hash(item['text'])
                
                # Construir metadata con información del modelo de embeddings
                meta = CanonicalMetadata(
                    client_id=client_id,
                    category=category,
                    access_level=access_level,
                    url=None,
                    source_timestamp=None,
                    # Metadata extra para tracking de versiones
                    embedding_model=os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001"),
                    embedding_dimension=3072
                )
                
                doc = CanonicalDocument(
                    content_id=chunk_id,
                    source=source,
                    title=f"{original_filename} (Pág. {item['page_number']})",
                    body_content=item['text'],
                    hash=chunk_hash,
                    metadata=meta
                )
                
                self.vector_store.upsert_document(doc)
                total_chars += len(item['text'])

            # 4. Actualizar Registro Maestro
            logger.info(f"Actualizando estado a SYNCED para {content_id}")
            self.vector_store.update_sync_status(client_id, content_id, "SYNCED")

            logger.info(f"ETL Exitoso: {len(pages_text)} fragmentos creados para {content_id}")
            
            return {
                "status": IngestStatus.SYNCED,
                "content_id": content_id,
                "chunks_processed": len(pages_text),
                "total_chars": total_chars
            }

        except Exception as e:
            logger.error(f"ETL Fallido para {content_id}: {e}")
            try:
                self.vector_store.update_sync_status(client_id, content_id, "FAILED", str(e))
            except:
                pass
            return {
                "status": IngestStatus.FAILED,
                "error": str(e)
            }

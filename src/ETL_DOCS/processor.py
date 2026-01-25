
import logging
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
                         source: SourceType = SourceType.PDF_UPLOAD) -> Dict[str, Any]:
        """
        Flujo principal de procesamiento.
        Retorna: Dict con resultado de la operación.
        """
        logger.info(f"Iniciando procesamiento ETL para: {original_filename} ({content_id})")

        try:
            # 1. Extracción de Texto
            extracted_text = self._extract_text_from_pdf(file_path)
            
            if not extracted_text:
                raise ValueError("El documento está vacío o no se pudo extraer texto legible.")

            # 2. Hashing (Calculado en VectorStore, pero podemos pre-calcular si hiciera falta)
            # 3. Construcción del Documento Canónico
            doc = CanonicalDocument(
                content_id=content_id,
                client_id=client_id,
                source=source,
                title=original_filename,
                body_content=extracted_text,
                hash="pending", # Se re-calcula real en el vector store o utils
                metadata={
                    "original_filename": original_filename,
                    "category": "knowledge_base", # Default category
                    "file_path": file_path
                }
            )
            
            # Ajuste: el hash es obligatorio en el modelo. Lo calculamos aquí para cumplir el contrato.
            doc.hash = self.vector_store.calculate_hash(extracted_text)

            # 4. Ingesta Inteligente (Vector Store)
            result = self.vector_store.upsert_document(doc)
            
            status = IngestStatus.SYNCED
            msg = "Documento procesado y sincronizado exitosamente."
            if result is True: # Si retornó True explícito (Upsert o Skip exitoso)
                 msg = "Sincronizado (Nuevo o Existente)."

            logger.info(f"ETL Exitoso: {msg}")
            
            return {
                "status": status,
                "content_id": content_id,
                "chars_extracted": len(extracted_text),
                "hash": doc.hash
            }

        except Exception as e:
            logger.error(f"ETL Fallido para {content_id}: {e}")
            return {
                "status": IngestStatus.FAILED,
                "error": str(e)
            }


import os
import json
import logging
import hashlib
from typing import Optional, List, Dict, Any
import hashlib
from typing import Optional, List, Dict, Any
import uuid
from uuid import UUID

import psycopg2
from psycopg2.extras import Json
import google.generativeai as genai
from dotenv import load_dotenv

from src.shared.schemas import CanonicalDocument

# Cargar configuración
load_dotenv()
logger = logging.getLogger(__name__)

# Configurar Google GenAI
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")

# Configurar DB
DB_HOST = os.getenv("DB_HOST", "192.168.0.31")
DB_NAME = os.getenv("DB_NAME", "agentic") # Usamos la variable de entorno, default agentic
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

class VectorStore:
    def __init__(self):
        self.conn = None
        self._connect()

    def _connect(self):
        """Establece conexión con la base de datos"""
        try:
            self.conn = psycopg2.connect(
                host=DB_HOST,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASS
            )
            # Habilitar autocommit para operaciones simples
            self.conn.autocommit = True
        except Exception as e:
            logger.error(f"Error conectando a DB Semantic: {e}")
            raise

    def get_embedding(self, text: str) -> List[float]:
        """Genera embedding usando Google Gemini"""
        try:
            # Gemini soporta task_type para optimizar (RETRIEVAL_DOCUMENT para guardar)
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=text,
                task_type="retrieval_document",
                title="Embedding generation" # Opcional pero recomendado por API
            )
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generando embedding con Google AI: {e}")
            raise

    def calculate_hash(self, content: str) -> str:
        """Calcula SHA-256 del contenido de texto"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def register_document_in_db(self, client_id: UUID, filename: str, storage_path: str, content_id: str, access_level: str = 'shared', category: str = 'General'):
        """Crea el registro inicial en ai_knowledge_documents como PENDING."""
        if not self.conn or self.conn.closed: self._connect()
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ai_knowledge_documents 
                (client_id, filename, storage_path, sync_status, content_hash, access_level, category, created_at)
                VALUES (%s, %s, %s, 'PENDING', %s, %s, %s, NOW())
            """, (str(client_id), filename, storage_path, content_id, access_level, category))

    def update_sync_status(self, client_id: UUID, content_id: str, status: str, error_message: str = None):
        """Actualiza el estado de sincronización y el hash final."""
        if not self.conn or self.conn.closed: self._connect()
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE ai_knowledge_documents 
                SET sync_status = %s, 
                    error_message = %s,
                    last_synced_at = NOW()
                WHERE client_id = %s AND content_hash = %s
            """, (status, error_message, str(client_id), content_id))

    def list_documents(self, client_id: UUID) -> List[Dict[str, Any]]:
        """Lista todos los documentos registrados para un cliente."""
        if not self.conn or self.conn.closed: self._connect()
        from psycopg2.extras import RealDictCursor
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, filename, sync_status, last_synced_at, created_at, content_hash as content_id, error_message, access_level, category
                FROM ai_knowledge_documents 
                WHERE client_id = %s
                ORDER BY created_at DESC
            """, (str(client_id),))
            return cur.fetchall()

    def upsert_document(self, doc: CanonicalDocument) -> bool:
        """
        Inserta o actualiza un documento en la tabla semantic_items.
        Lógica:
        1. Verifica hash existente para este content_id y client_id.
        2. Si el hash es igual -> SKIP (Idempotencia).
        3. Si cambió o es nuevo -> Generar Embedding -> UPSERT.
        """
        if not self.conn or self.conn.closed:
            self._connect()

        try:
            with self.conn.cursor() as cur:
                # 1. Verificar existencia y hash
                cur.execute("""
                    SELECT id, hash FROM ai_vectors 
                    WHERE client_id = %s AND content_id = %s
                """, (str(doc.metadata.client_id), doc.content_id))
                
                row = cur.fetchone()
                existing_id = row[0] if row else None
                existing_hash = row[1] if row else None
                # Calcular hash actual
                current_hash = self.calculate_hash(doc.body_content)
                
                # LOGIC CHECK: ¿Necesitamos actualizar?
                if existing_hash == current_hash:
                    logger.info(f"SKIP Upsert: El documento {doc.content_id} no ha cambiado.")
                    return True # Exitoso (porque ya estaba bien)

                logger.info(f"Procesando Upsert para {doc.content_id}...")
                
                # 2. Generar Embedding (Solo si es nuevo o cambió)
                embedding_vector = self.get_embedding(doc.body_content)

                # Asegurar que metadata sea JSON válido
                # Convertir modelo Pydantic a dict compatible con JSON (UUIDs a string)
                if hasattr(doc.metadata, "model_dump"):
                    meta_dict = doc.metadata.model_dump(mode='json')
                else:
                    meta_dict = doc.metadata
                meta_json = Json(meta_dict)

                # 3. UPSERT Manual (Evitar ON CONFLICT si falta índice compuesto)
                if existing_id:
                    # UPDATE Exitsente
                    sql = """
                        UPDATE ai_vectors 
                        SET body_content = %s,
                            title = %s,
                            metadata = %s,
                            hash = %s,
                            embedding = %s,
                            updated_at = NOW()
                        WHERE id = %s;
                    """
                    cur.execute(sql, (
                        doc.body_content,
                        doc.title,
                        meta_json,
                        current_hash,
                        embedding_vector,
                        existing_id
                    ))
                    logger.info(f"Update realizado para: {doc.content_id}")
                else:
                    # INSERT Nuevo
                    try:
                        sql = """
                            INSERT INTO ai_vectors 
                            (id, content_id, client_id, source, title, body_content, metadata, hash, embedding, updated_at, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW());
                        """
                        new_id = str(uuid.uuid4())
                        cur.execute(sql, (
                            new_id,
                            doc.content_id,
                            str(doc.metadata.client_id),
                            doc.source,
                            doc.title,
                            doc.body_content,
                            meta_json,
                            current_hash,
                            embedding_vector
                        ))
                        logger.info(f"Insert realizado para: {doc.content_id} (ID: {new_id})")
                    except psycopg2.errors.UniqueViolation as e:
                        # Si falla por hash key, significa que OTRO documento tiene exactamente el mismo contenido
                        # Esto es la validación DB de idempotencia. 
                        logger.warning(f"Hash duplicado detectado en DB para {doc.content_id}. El contenido ya existe bajo otro ID. {e}")
                        # En este modelo de negocio, decidimos: ¿Permitimos duplicados de contenido con diferente ID?
                        # Si la tabla tiene UNIQUE(hash), NO se permite.
                        # Retornamos True asumiendo que "ya está preservado el conocimiento".
                        self.conn.rollback() # Resetear transacción fallida
                        return True

                return True

        except Exception as e:
            logger.error(f"Error en BD durante upsert: {e}")
            self.conn.rollback() # Rollback manual si falla algo en un bloque no-autocommit implícito
            raise

    def delete_document(self, client_id: UUID, content_id: str) -> Optional[str]:
        """Borra un documento de ambas tablas y retorna el nombre del archivo para limpieza física."""
        if not self.conn or self.conn.closed:
            self._connect()
        
        filename = None
        with self.conn.cursor() as cur:
            # 0. Obtener el nombre del archivo antes de borrar el registro
            cur.execute("""
                SELECT filename FROM ai_knowledge_documents 
                WHERE client_id = %s AND content_hash = %s
            """, (str(client_id), content_id))
            row = cur.fetchone()
            if row:
                filename = row[0]

            # 1. Borrar vectores (el documento base y sus fragmentos)
            cur.execute("""
                DELETE FROM ai_vectors 
                WHERE client_id = %s AND (content_id = %s OR content_id LIKE %s)
            """, (str(client_id), content_id, f"{content_id}_part_%"))
            
            # 2. Borrar registro maestro
            cur.execute("""
                DELETE FROM ai_knowledge_documents 
                WHERE client_id = %s AND content_hash = %s
            """, (str(client_id), content_id))
            
        return filename
    
    def delete_client(self, client_id: UUID):
        """Borra TODO de un cliente en ambas tablas."""
        if not self.conn or self.conn.closed:
            self._connect()
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM ai_vectors WHERE client_id = %s", (str(client_id),))
            cur.execute("DELETE FROM ai_knowledge_documents WHERE client_id = %s", (str(client_id),))


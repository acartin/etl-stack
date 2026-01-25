
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
                """, (str(doc.client_id), doc.content_id))
                
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
                meta_json = Json(doc.metadata)

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
                            str(doc.client_id),
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

    def delete_document(self, client_id: UUID, content_id: str):
        """Borra un documento especifico"""
        if not self.conn or self.conn.closed:
            self._connect()
        with self.conn.cursor() as cur:
            cur.execute("""
                DELETE FROM ai_vectors 
                WHERE client_id = %s AND content_id = %s
            """, (str(client_id), content_id))
    
    def delete_client(self, client_id: UUID):
        """Borra TODOS los documentos de un cliente"""
        if not self.conn or self.conn.closed:
            self._connect()
        with self.conn.cursor() as cur:
            cur.execute("""
                DELETE FROM ai_vectors 
                WHERE client_id = %s
            """, (str(client_id),))


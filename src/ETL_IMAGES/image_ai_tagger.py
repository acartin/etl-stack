import os
import json
import time
import psycopg2
import google.generativeai as genai
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import logging

# Configuración básica de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("AI_TAGGER")

# Cargar entorno
load_dotenv("/app/src/.env")

# Configurar Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    logger.error("❌ No se encontró GOOGLE_API_KEY en variables de entorno.")
    exit(1)

genai.configure(api_key=GOOGLE_API_KEY)

# Modelo: Usamos Flash para velocidad y eficiencia en visión
MODEL_NAME = os.getenv("VISION_MODEL", "gemini-2.0-flash")

class ImageAITagger:
    def __init__(self):
        self.conn = self.get_db_connection()
        self.model = genai.GenerativeModel(MODEL_NAME)
        self.storage_root = "/app/storage/images"

    def get_db_connection(self):
        return psycopg2.connect(
            host=os.getenv("DB_HOST", "192.168.0.31"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "agentic"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            cursor_factory=RealDictCursor
        )

    def get_pending_images(self, limit=5):
        """
        Obtiene imágenes pendientes de procesar.
        ESTRATEGIA: Prioridad a las imágenes principales (is_main = true).
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, property_id, local_path, content_hash 
                FROM public.lead_property_images 
                WHERE is_processed = FALSE 
                AND is_main = TRUE
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return cur.fetchall()

    def analyze_image(self, image_path: str):
        """
        Envía la imagen a Gemini y retorna el JSON estructurado.
        """
        try:
            full_path = os.path.join(self.storage_root, image_path)
            
            if not os.path.exists(full_path):
                logger.warning(f"⚠️ Archivo no encontrado: {full_path}")
                return None

            # Cargar imagen en memoria para la API (MIME type image/webp)
            with open(full_path, "rb") as f:
                image_data = f.read()

            prompt = """
            Actúa como un inspector técnico inmobiliario. Analiza esta imagen con precisión objetiva.
            
            Tu objetivo es generar metadatos estructurados ("Hard Data") para clasificación de inventario.
            Responde ÚNICAMENTE con un objeto JSON válido con estas claves:
            {
                "room_type": "Clasifica en UNA categoría: 'Fachada', 'Cocina', 'Sala', 'Comedor', 'Dormitorio', 'Baño', 'Terraza/Balcón', 'Jardín/Patio', 'Piscina', 'Terreno/Lote', 'Vista Panorámica', 'Garaje', 'Oficina', 'Bodega', 'Plano/Render', 'Mapa', 'Otro'",
                "features": ["Lista de características técnicas visibles (ej: 'topografía plana', 'árboles', 'cercado', 'isla central', 'cielos altos', 'piso porcelanato', 'walk-in closet'). Máximo 8 tags."],
                "materials": ["Lista de materiales predominantes (ej: 'concreto', 'block', 'vidrio', 'madera', 'gypsum', 'tierra', 'zacate')"],
                "condition": "Estado aparente: 'Nuevo', 'Excelente', 'Bueno', 'Regular', 'Para Remodelar', 'Obra Gris', 'En Construcción'",
                "quality_score": 8 (Entero 1-10 evaluando calidad técnica de la foto. 1=Borrosa/Mala, 10=Profesional de Revista)
            }
            Si la imagen es solo un logo o texto irrelevante, clasifica como 'Otro' y quality_score bajo.
            """

            # Generar contenido
            contents = [
                {"mime_type": "image/webp", "data": image_data},
                prompt
            ]
            
            response = self.model.generate_content(contents)
            
            # Limpiar posible markdown
            text_response = response.text.replace("```json", "").replace("```", "").strip()
            
            return json.loads(text_response)

        except Exception as e:
            logger.error(f"❌ Error analizando imagen {image_path}: {e}")
            return None

    def save_tags(self, image_id, tags_json):
        """Guarda los tags y marca como procesada."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE public.lead_property_images
                    SET vision_labels = %s,
                        is_processed = TRUE,
                        updated_at = NOW()
                    WHERE id = %s
                """, (json.dumps(tags_json, ensure_ascii=False), image_id))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error guardando en DB: {e}")
            self.conn.rollback()
            return False

    def run_full_process(self, batch_size=10, max_total_images=50):
        logger.info(f"🚀 Iniciando Proceso Completo de Etiquetado AI (Lotes de {batch_size}, Límite Total: {max_total_images})...")
        
        total_processed = 0
        
        while True:
            if total_processed >= max_total_images:
                logger.info(f"🛑 Se alcanzó el límite de seguridad de {max_total_images} imágenes procesadas por ejecución.")
                break

            # Ajustar el límite de la consulta SQL si queda menos cupo que el batch_size
            remaining = max_total_images - total_processed
            current_batch_size = min(batch_size, remaining)
            
            images = self.get_pending_images(current_batch_size)
            
            if not images:
                logger.info("😴 No hay más imágenes principales pendientes. ¡Trabajo terminado!")
                break

            logger.info(f"📸 Procesando lote de {len(images)} imágenes... (Procesadas hoy: {total_processed})")
            
            for img in images:
                logger.info(f"🤖 Analizando: {img['local_path'][:30]}... (ID: {img['id']})")
                
                start_time = time.time()
                tags = self.analyze_image(img['local_path'])
                duration = time.time() - start_time
                
                if tags:
                    success = self.save_tags(img['id'], tags)
                    if success:
                        logger.info(f"✅ OK ({duration:.2f}s) | {tags.get('room_type')} | Q:{tags.get('quality_score')}")
                        total_processed += 1
                    else:
                        logger.warning("⚠️ Fallo guardando en DB.")
                else:
                    logger.warning("⚠️ Fallo análisis AI (Posible error de API o imagen corrupta).")
                
                # Pausa mínima para no saturar la API
                time.sleep(1.5)

if __name__ == "__main__":
    tagger = ImageAITagger()
    # Límite duro de 100 imágenes para evitar costos, ajustable según necesidad
    tagger.run_full_process(batch_size=10, max_total_images=100)

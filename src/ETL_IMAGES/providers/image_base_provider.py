import os
import requests
import hashlib
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from PIL import Image
import logging

# Configuración de logs básica para el módulo
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageBaseProvider(ABC):
    """
    Clase base para la extracción y procesamiento de imágenes.
    Sigue la simetría de ETL_PROPERTIES.
    """

    def __init__(self):
        self.staging_root = "/app/staging/ETL_IMAGES/tmp"
        self.storage_root = "/app/storage/images"
        
        # El loader se encargará de crear las carpetas específicas por propiedad
        os.makedirs(self.staging_root, exist_ok=True)
        os.makedirs(self.storage_root, exist_ok=True)

    @abstractmethod
    def get_image_urls(self, raw_snapshot: Dict[str, Any]) -> List[str]:
        """
        Cada provider específico sabe dónde buscar las URLs de las fotos
        en el snapshot crudo del JSON del tema correspondiente.
        """
        pass

    def generate_content_hash(self, data: bytes) -> str:
        """Genera un hash SHA-256 del contenido binario de la imagen."""
        return hashlib.sha256(data).hexdigest()

    def download_image(self, url: str, client_id: str, property_id: str) -> Dict[str, Any]:
        """
        Descarga la imagen a staging, calcula su hash y retorna metadatos.
        """
        try:
            response = requests.get(url, timeout=15, stream=True)
            response.raise_for_status()
            
            content = response.content
            content_hash = self.generate_content_hash(content)
            
            # Determinar extensión
            ext = os.path.splitext(url)[1].lower() or ".jpg"
            if "?" in ext: ext = ext.split("?")[0]
            
            # Ruta temporal en staging
            temp_path = os.path.join(self.staging_root, f"{content_hash}{ext}")
            
            with open(temp_path, 'wb') as f:
                f.write(content)
            
            return {
                "temp_path": temp_path,
                "content_hash": content_hash,
                "original_url": url,
                "extension": ext
            }
        except Exception as e:
            logger.error(f"❌ Error descargando {url}: {e}")
            return None

    def process_and_store(self, download_info: Dict[str, Any], client_id: str, property_id: str) -> str:
        """
        Optimiza a WebP y mueve al almacenamiento definitivo jerárquico.
        Retorna la ruta relativa final para la DB.
        """
        if not download_info:
            return None

        source_path = download_info["temp_path"]
        content_hash = download_info["content_hash"]
        
        # Estructura: /app/storage/images/{client_id}/properties/{property_id}/{hash}.webp
        relative_path = os.path.join(str(client_id), "properties", str(property_id), f"{content_hash}.webp")
        final_abs_path = os.path.join(self.storage_root, relative_path)
        
        # Asegurar directorio de destino
        os.makedirs(os.path.dirname(final_abs_path), exist_ok=True)

        if os.path.exists(final_abs_path):
            # Limpiar staging si ya existe en storage
            if os.path.exists(source_path):
                os.remove(source_path)
            return relative_path

        try:
            with Image.open(source_path) as img:
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                img.save(final_abs_path, "WEBP", quality=80, optimize=True)
                
            # Limpiar staging después de procesar
            if os.path.exists(source_path):
                os.remove(source_path)
                
            logger.info(f"✨ Imagen optimizada y guardada: {relative_path}")
            return relative_path
        except Exception as e:
            logger.error(f"❌ Error procesando {source_path}: {e}")
            return None

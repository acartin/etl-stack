from typing import List, Dict, Any
from .image_base_provider import ImageBaseProvider

class ImageRealHomesProvider(ImageBaseProvider):
    """
    Extracción de imágenes para el tema RealHomes.
    """

    def get_image_urls(self, property_data: Dict[str, Any]) -> List[str]:
        """
        Extrae URLs de la galería completa.
        1. Busca en la lista normalizada 'images' de la ingesta.
        2. Busca en el snapshot crudo (REAL_HOMES_property_images).
        3. Prioriza calidad (full_url > large > url).
        """
        urls = []
        
        # 1. Fallback inicial: Si ya fueron parseadas en la ingesta (ej. Yoast)
        norm_images = property_data.get("images", [])
        if norm_images:
            urls.extend(norm_images)

        # 2. Galería Completa de RealHomes
        raw_snapshot = property_data.get("raw_data_snapshot", {})
        meta = raw_snapshot.get("property_meta", {})
        images_list = meta.get("REAL_HOMES_property_images", [])

        if isinstance(images_list, list):
            for img in images_list:
                if not isinstance(img, dict): continue
                
                # Intentar obtener la mejor URL posible
                best_url = None
                
                # Opción A: full_url
                if img.get("full_url"):
                    best_url = img["full_url"]
                # Opción B: sizes.large
                elif "sizes" in img and isinstance(img["sizes"], dict):
                    large = img["sizes"].get("large")
                    if large and isinstance(large, dict):
                        best_url = large.get("url")
                # Opción C: url base (a veces es el full, a veces no)
                elif img.get("url"):
                    best_url = img["url"]

                if best_url and best_url not in urls:
                    urls.append(best_url)
        
        return urls

from typing import List, Dict, Any
from .image_base_provider import ImageBaseProvider

class ImageRealHomesProvider(ImageBaseProvider):
    """
    Extracción de imágenes para el tema RealHomes.
    """

    def get_image_urls(self, property_data: Dict[str, Any]) -> List[str]:
        """
        Extrae URLs de la clave REAL_HOMES_property_images.
        Prioriza la versión 'large' por eficiencia, cae a 'full_url' si no existe.
        """
        urls = []
        # Buscamos en el snapshot del provider
        raw_snapshot = property_data.get("raw_data_snapshot", {})
        meta = raw_snapshot.get("property_meta", {})
        images_list = meta.get("REAL_HOMES_property_images", [])

        if not isinstance(images_list, list):
            # A veces WordPress devuelve metadatos serializados o en formatos raros
            return []

        for img in images_list:
            # Intentamos obtener la versión 'large'
            sizes = img.get("sizes", {})
            large_url = sizes.get("large", {}).get("url")
            
            if large_url:
                urls.append(large_url)
            else:
                # Si no hay large, usamos la full_url
                full_url = img.get("full_url")
                if full_url:
                    urls.append(full_url)
        
        return urls

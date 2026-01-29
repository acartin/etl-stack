from typing import List, Dict, Any
from .image_base_provider import ImageBaseProvider

class ImageHouzezProvider(ImageBaseProvider):
    """
    Extracción de imágenes para el tema Houzez.
    """

    def get_image_urls(self, property_data: Dict[str, Any]) -> List[str]:
        """
        En Houzez, el scraper suele normalizar las imágenes en la raíz del objeto.
        Si hay metadatos adicionales en el snapshot, podríamos intentar resolverlos,
        pero por ahora usamos el array 'images' que ya viene normalizado.
        """
        # A diferencia de RealHomes, aquí property_data es el objeto completo
        # para tener acceso al array 'images' ya normalizado por el scraper de propiedades.
        urls = property_data.get("images", [])
        
        # Si no hay nada en el array principal, buscamos en el snapshot por si acaso
        if not urls:
            raw = property_data.get("raw_data_snapshot", {})
            # Algunos scrapers de Houzez guardan la destacada en featured_image_url
            featured = raw.get("featured_image_url")
            if featured:
                urls = [featured]
                
        return urls

from typing import List, Dict, Any
from .image_base_provider import ImageBaseProvider

class ImageWPResidenceProvider(ImageBaseProvider):
    """
    Extracción de imágenes para el tema WP Residence / WP Estate.
    """

    def get_image_urls(self, property_data: Dict[str, Any]) -> List[str]:
        """
        En WP Residence, el scraper suele normalizar las imágenes en la raíz del objeto.
        """
        return property_data.get("images", [])

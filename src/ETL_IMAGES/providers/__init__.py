from .image_base_provider import ImageBaseProvider
from .image_realhomes_provider import ImageRealHomesProvider
from .image_houzez_provider import ImageHouzezProvider
from .image_wp_residence_provider import ImageWPResidenceProvider

def get_image_provider(provider_type: str) -> ImageBaseProvider:
    """Factory para obtener el provider de imagen correcto."""
    providers = {
        "realhomes": ImageRealHomesProvider,
        "houzez": ImageHouzezProvider,
        "wp_residence": ImageWPResidenceProvider
    }
    provider_class = providers.get(provider_type.lower())
    return provider_class() if provider_class else None

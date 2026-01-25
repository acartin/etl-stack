import random
import requests
import time
from typing import List, Dict, Any
from .base_provider import BaseRealEstateProvider

class RealHomesProvider(BaseRealEstateProvider):
    """
    Especialista para temas RealHomes.
    Usa la WP REST API para obtener listados y metadatos (property_meta).
    """

    def __init__(self, site_name: str, base_url: str, api_endpoint: str = "/wp-json/wp/v2/propiedad"):
        super().__init__(site_name, base_url)
        self.api_url = f"{self.base_url}{api_endpoint}"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def get_links(self) -> List[Dict[str, Any]]:
        links = []
        page = 1
        print(f"📡 Buscando propiedades en {self.site_name}...")
        
        while True:
            try:
                # Reducimos a 20 por página para no alertar firewalls
                params = {"per_page": 20, "page": page, "_fields": "id,link,slug"}
                response = requests.get(self.api_url, headers=self.headers, params=params, timeout=10)
                
                if response.status_code == 400: break
                response.raise_for_status()
                
                batch = response.json()
                if not batch: break
                
                for item in batch:
                    links.append({"wp_id": item["id"], "url": item["link"], "slug": item["slug"]})
                
                total_pages = int(response.headers.get("X-WP-TotalPages", 1))
                print(f"   - Pagina {page}/{total_pages} leída...")
                
                if page >= total_pages: break
                page += 1
                time.sleep(1) # Pausa de seguridad
            except Exception as e:
                print(f"❌ Error obteniendo links en página {page}: {e}")
                break
        
        print(f"✅ Se encontraron {len(links)} propiedades.")
        return links

    def extract_property_details(self, url: str, **kwargs) -> Dict[str, Any]:
        """
        Extrae detalles usando el slug (vía API para mayor precisión).
        """
        slug = kwargs.get("slug")
        if not slug: return {}

        try:
            params = {"slug": slug}
            response = requests.get(self.api_url, headers=self.headers, params=params, timeout=15)
            response.raise_for_status()
            
            data_list = response.json()
            if not isinstance(data_list, list) or not data_list: return {}
            
            item = data_list[0]
            meta = item.get("property_meta", {})
            if not isinstance(meta, dict): meta = {}
            loc = meta.get("REAL_HOMES_property_location", {})
            if not isinstance(loc, dict): loc = {}

            # Extraer imagen principal de Yoast
            images = []
            yoast = item.get("yoast_head_json", {})
            if yoast and "og_image" in yoast:
                for img in yoast["og_image"]:
                    if isinstance(img, dict) and img.get("url"):
                        images.append(img["url"])

            # Mapeo crudo pero estructurado para el normalizador
            raw_result = {
                "external_id": str(item.get("id")),
                "title": item.get("title", {}).get("rendered") if isinstance(item.get("title"), dict) else "Sin título",
                "url": item.get("link"),
                "price": meta.get("REAL_HOMES_property_price"),
                "area_sqm": meta.get("REAL_HOMES_property_size"),
                "bedrooms": meta.get("REAL_HOMES_property_bedrooms"),
                "bathrooms": meta.get("REAL_HOMES_property_bathrooms"),
                "lat": loc.get("latitude"),
                "lng": loc.get("longitude"),
                "images": images,
                "raw": item
            }
            return self.normalize_data(raw_result)

        except Exception as e:
            print(f"❌ Error en detalle de {slug}: {e}")
            return {}


import random
import requests
import time
from typing import List, Dict, Any
from .base_provider import BaseRealEstateProvider

class WPResidenceProvider(BaseRealEstateProvider):
    """
    Especialista para el tema WP Residence (como Terraquea).
    Usa el endpoint /wp-json/wp/v2/estate_property y busca en 'all_meta'.
    """

    def __init__(self, site_name: str, base_url: str, api_endpoint: str = "/wp-json/wp/v2/estate_property"):
        super().__init__(site_name, base_url)
        self.api_url = f"{self.base_url}{api_endpoint}"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def get_links(self) -> List[Dict[str, Any]]:
        links = []
        page = 1
        print(f"📡 Buscando propiedades en {self.site_name} (WP Residence)...")
        
        while True:
            try:
                params = {"per_page": 20, "page": page, "_fields": "id,link,slug,modified_gmt"}
                response = requests.get(self.api_url, headers=self.headers, params=params, timeout=10)
                
                if response.status_code == 400: break # Fin de páginas
                response.raise_for_status()
                
                batch = response.json()
                if not batch: break
                
                for item in batch:
                    links.append({
                        "wp_id": item["id"], 
                        "url": item["link"], 
                        "slug": item["slug"],
                        "modified_gmt": item.get("modified_gmt")
                    })
                
                total_pages = int(response.headers.get("X-WP-TotalPages", 1))
                print(f"   - Pagina {page}/{total_pages} leída...")
                
                if page >= total_pages: break
                page += 1
                # Modo Caballero: Delay entre páginas de listado
                wait_time = random.uniform(3, 6)
                print(f"   ... esperando {wait_time:.2f}s para la siguiente página...")
                time.sleep(wait_time)
            except Exception as e:
                print(f"❌ Error obteniendo links en página {page}: {e}")
                break
        
        print(f"✅ Se encontraron {len(links)} propiedades.")
        return links

    def extract_property_details(self, url: str, **kwargs) -> Dict[str, Any]:
        slug = kwargs.get("slug")
        if not slug: return {}

        try:
            params = {"slug": slug}
            response = requests.get(self.api_url, headers=self.headers, params=params, timeout=15)
            response.raise_for_status()
            
            data_list = response.json()
            if not isinstance(data_list, list) or not data_list: return {}
            
            item = data_list[0]
            # WP Residence suele poner los metadatos en 'all_meta' o directamente en la raíz mediante plugins
            meta = item.get("all_meta", {})
            
            # Imágenes de Yoast
            images = []
            yoast = item.get("yoast_head_json", {})
            if yoast and "og_image" in yoast:
                for img in yoast["og_image"]:
                    if isinstance(img, dict) and img.get("url"):
                        images.append(img["url"])

            # Tratamiento de coordenadas
            lat = meta.get("property_latitude")
            lng = meta.get("property_longitude")
            if lat == "0" or lat == 0: lat = None
            if lng == "0" or lng == 0: lng = None

            raw_result = {
                "external_id": str(item.get("id")),
                "title": item.get("title", {}).get("rendered") if isinstance(item.get("title"), dict) else "Sin título",
                "url": item.get("link"),
                "price": meta.get("property_price"),
                "currency": meta.get("currency_selection"),
                "area_sqm": meta.get("property_size"),
                "bedrooms": meta.get("property_bedrooms"),
                "bathrooms": meta.get("property_bathrooms"),
                "lat": lat,
                "lng": lng,
                "address": meta.get("property_address"),
                "images": images,
                "raw": item
            }
            return self.normalize_data(raw_result)

        except Exception as e:
            print(f"❌ Error en detalle de {slug} (Terraquea): {e}")
            return {}


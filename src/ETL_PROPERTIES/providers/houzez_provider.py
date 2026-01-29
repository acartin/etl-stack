import random
import requests
import time
from typing import List, Dict, Any
from .base_provider import BaseRealEstateProvider

class HouzezProvider(BaseRealEstateProvider):
    """
    Especialista para temas Houzez (ej: AltaVista).
    Usa la WP REST API con metadatos prefijados con 'fave_'.
    """

    def __init__(self, site_name: str, base_url: str, api_endpoint: str = "/wp-json/wp/v2/properties"):
        super().__init__(site_name, base_url)
        self.api_url = f"{self.base_url}{api_endpoint}"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def get_links(self) -> List[Dict[str, Any]]:
        links = []
        page = 1
        print(f"📡 Buscando propiedades en {self.site_name} (Houzez)...")
        
        while True:
            try:
                # Usamos per_page=20 como medida de seguridad
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
                time.sleep(1) 
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
            meta = item.get("property_meta", {})
            if not isinstance(meta, dict): meta = {}

            # Houzez guarda los valores en listas, ej: "fave_property_price": ["140000"]
            def get_first(key):
                val = meta.get(key)
                return val[0] if isinstance(val, list) and val else val

            # Procesar coordenadas (vienen como "lat,lng,zoom")
            lat, lng = None, None
            coords_raw = get_first("fave_property_location")
            if coords_raw and "," in str(coords_raw):
                parts = str(coords_raw).split(",")
                if len(parts) >= 2:
                    lat, lng = parts[0].strip(), parts[1].strip()

            # Extraer imágenes de Yoast
            images = []
            yoast = item.get("yoast_head_json", {})
            if yoast and "og_image" in yoast:
                for img in yoast["og_image"]:
                    if isinstance(img, dict) and img.get("url"):
                        images.append(img["url"])

            raw_result = {
                "external_id": str(item.get("id")), # ID Inmutable de WP
                "title": item.get("title", {}).get("rendered") if isinstance(item.get("title"), dict) else "Sin título",
                "url": item.get("link"),
                "price": get_first("fave_property_price"),
                "area_sqm": get_first("fave_property_size"),
                "bedrooms": get_first("fave_property_bedrooms"),
                "bathrooms": get_first("fave_property_bathrooms"),
                "lat": lat,
                "lng": lng,
                "address": get_first("fave_property_map_address"),
                "images": images,
                "raw": item
            }
            return self.normalize_data(raw_result)

        except Exception as e:
            print(f"❌ Error en detalle de {slug} (Houzez): {e}")
            return {}

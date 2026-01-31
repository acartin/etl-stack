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
        use_modified_gmt = True
        print(f"📡 Buscando propiedades en {self.site_name} (Houzez)...")
        
        while True:
            try:
                fields = "id,link,slug"
                if use_modified_gmt:
                    fields += ",modified_gmt"

                params = {"per_page": 20, "page": page, "_fields": fields}
                response = requests.get(self.api_url, headers=self.headers, params=params, timeout=10)
                
                if response.status_code == 400:
                    # Si falla por modified_gmt en la primera página, reintentamos sin el campo
                    if use_modified_gmt and page == 1:
                        print(f"⚠️ {self.site_name} no soporta 'modified_gmt' en API. Reintentando sin filtrado de fecha...")
                        use_modified_gmt = False
                        continue
                    break # Fin de páginas
                
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
                # Sleep aleatorio por cada página de links
                time.sleep(random.uniform(1.0, 3.0)) 
            except Exception as e:
                print(f"❌ Error obteniendo links en página {page}: {e}")
                break
        
        print(f"✅ Se encontraron {len(links)} propiedades.")
        return links

    def extract_property_details(self, url: str, **kwargs) -> Dict[str, Any]:
        slug = kwargs.get("slug")
        if not slug: return {}

        try:
            # Usar _embed=true para capturar taxonomías (amenidades) si existen
            params = {"slug": slug, "_embed": "true"}
            response = requests.get(self.api_url, headers=self.headers, params=params, timeout=15)
            response.raise_for_status()
            
            data_list = response.json()
            if not isinstance(data_list, list) or not data_list: return {}
            
            item = data_list[0]
            meta = item.get("property_meta", {})
            if not isinstance(meta, dict): meta = {}

            # Función helper para obtener valores de Houzez (vienen en listas)
            def get_first(key):
                val = meta.get(key)
                return val[0] if isinstance(val, list) and val else val

            # Procesar coordenadas
            lat, lng = None, None
            coords_raw = get_first("fave_property_location")
            if coords_raw and "," in str(coords_raw):
                parts = str(coords_raw).split(",")
                if len(parts) >= 2:
                    lat, lng = parts[0].strip(), parts[1].strip()

            # Capturar amenidades desde _embedded (WP Taxonomies)
            amenities = []
            if "_embedded" in item and "wp:term" in item["_embedded"]:
                for term_list in item["_embedded"]["wp:term"]:
                    for term in term_list:
                        # En Houzez la taxonomía suele llamarse 'property_feature'
                        if term.get("taxonomy") == "property_feature":
                            amenities.append(term.get("name"))

            # Construir diccionario de features detallado
            features = {
                "garage": get_first("fave_property_garage"),
                "parking_external": get_first("fave_property_garage_size"),
                "lot_size_sqm": get_first("fave_property_land"),
                "property_id_internal": get_first("fave_property_id"),
                "address": get_first("fave_property_map_address"),
                "amenities": amenities,
                # Campos base redundantes para el normalizador
                "bedrooms": get_first("fave_property_bedrooms"),
                "bathrooms": get_first("fave_property_bathrooms"),
            }

            # Extraer imágenes de Yoast
            images = []
            yoast = item.get("yoast_head_json", {})
            if yoast and "og_image" in yoast:
                for img in yoast["og_image"]:
                    if isinstance(img, dict) and img.get("url"):
                        images.append(img["url"])

            raw_result = {
                "external_id": str(item.get("id")),
                "title": item.get("title", {}).get("rendered") if isinstance(item.get("title"), dict) else "Sin título",
                "url": item.get("link"),
                "price": get_first("fave_property_price"),
                "area_sqm": get_first("fave_property_size"),
                "bedrooms": get_first("fave_property_bedrooms"),
                "bathrooms": get_first("fave_property_bathrooms"),
                "lat": lat,
                "lng": lng,
                "address": get_first("fave_property_map_address"),
                "features": features,
                "images": images,
                "raw": item
            }
            return self.normalize_data(raw_result)

        except Exception as e:
            print(f"❌ Error en detalle de {slug} (Houzez): {e}")
            return {}

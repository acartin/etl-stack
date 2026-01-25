import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime

class BaseRealEstateProvider(ABC):
    """
    Clase base abstracta para todos los proveedores de datos inmobiliarios.
    Define el contrato que cada tema (Houzez, RealHomes, etc.) debe cumplir.
    """

    def __init__(self, site_name: str, base_url: str):
        self.site_name = site_name
        self.base_url = base_url.rstrip("/")
        self.extracted_data = []

    @abstractmethod
    def get_links(self) -> List[Dict[str, Any]]:
        """Descubre todas las URLs de propiedades (usualmente via API o Sitemap)."""
        pass

    @abstractmethod
    def extract_property_details(self, url: str, **kwargs) -> Dict[str, Any]:
        """Extrae la ficha técnica de una URL específica."""
        pass

    def normalize_data(self, raw_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asegura que el dato final tenga el formato 'Canonical' para la tabla Stage.
        """
        return {
            "source_site": self.site_name,
            "ingested_at": datetime.utcnow().isoformat(),
            "external_id": raw_item.get("external_id"),
            "title": raw_item.get("title"),
            "price": raw_item.get("price"),
            "currency": raw_item.get("currency", "USD"),
            "sqm": raw_item.get("area_sqm"),
            "location": {
                "lat": raw_item.get("lat"),
                "lng": raw_item.get("lng"),
                "address": raw_item.get("address")
            },
            "features": {
                "bedrooms": raw_item.get("bedrooms"),
                "bathrooms": raw_item.get("bathrooms"),
                "garage": raw_item.get("garage")
            },
            "url": raw_item.get("url"),
            "images": raw_item.get("images", []),
            "raw_data_snapshot": raw_item.get("raw") # Por seguridad
        }

    def save_to_json(self, filename: str, client_id: str = None):
        """Guarda los resultados normalizados en un archivo JSON."""
        metadata = {
            "site": self.site_name,
            "url": self.base_url,
            "total_count": len(self.extracted_data),
            "timestamp": datetime.utcnow().isoformat()
        }
        if client_id:
            metadata["client_id"] = client_id

        output = {
            "metadata": metadata,
            "properties": self.extracted_data
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        print(f"📁 Datos guardados en {filename}")

    def load_existing_data(self, filename: str):
        """Carga datos previos de un JSON para permitir reanudación."""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.extracted_data = data.get("properties", [])
                print(f"📥 Se cargaron {len(self.extracted_data)} registros previos de {filename}")
        except FileNotFoundError:
            # print(f"ℹ️ No se encontró archivo previo en {filename}. Iniciando desde cero.")
            self.extracted_data = []
        except Exception as e:
            print(f"⚠️ Error cargando datos previos: {e}")
            self.extracted_data = []

    def run_full_extraction(self, limit: int = None, output_path: str = None, client_id: str = None, known_data: dict = None):
        """
        Ejecuta la extracción inteligente de todos los enlaces descubiertos.
        
        Args:
            limit: Máximo de propiedades a extraer.
            output_path: Ruta para guardado incremental.
            client_id: ID del cliente.
            known_data: Diccionario {external_id: last_updated_at} para sincronización inteligente.
        """
        import random
        import time
        from datetime import datetime

        links = self.get_links()
        if limit: links = links[:limit]

        if known_data is None: known_data = {}

        # Mapeo de lo que ya tenemos en el JSON local para no repetir en la misma sesión
        local_data = {str(p.get("external_id")): p.get("ingested_at") for p in self.extracted_data}
        
        newly_extracted = 0
        skipped_count = 0
        updated_count = 0

        for i, link_data in enumerate(links):
            ext_id = str(link_data.get("wp_id") or link_data.get("external_id", ""))
            
            # --- Lógica de Sincronización Inteligente (Opción B) ---
            should_extract = True
            reason = "Nueva propiedad"

            # 1. Priorizar SIEMPRE la fecha de la Base de Datos (Verdad de Producción)
            # Solo usamos la del JSON si la propiedad no existe aún en la base de datos.
            last_local_update = known_data.get(ext_id) or local_data.get(ext_id)
            
            if last_local_update:
                source_mod_str = link_data.get("modified_gmt")
                if source_mod_str:
                    try:
                        # Convertir fechas a objetos datetime para comparar
                        # WordPress: 2026-01-22T16:09:54 (ISO aprox)
                        # Normalizar fechas para comparación (segundos de precision)
                        source_ts = int(datetime.fromisoformat(source_mod_str.replace("Z", "")).timestamp())
                        
                        if isinstance(last_local_update, str):
                            local_ts = int(datetime.fromisoformat(last_local_update.replace("Z", "")).timestamp())
                        else:
                            local_ts = int(last_local_update.timestamp())

                        # Tolerancia de 60 segundos por desfases de sistema
                        if source_ts <= (local_ts + 60):
                            should_extract = False
                            skipped_count += 1
                        else:
                            reason = f"Actualización detectada ({source_mod_str} > {last_local_update})"
                            updated_count += 1
                    except Exception as e:
                        print(f"⚠️ Error comparando fechas para {ext_id}: {e}")
                else:
                    # Si no hay fecha en el sitio, por seguridad no la bajamos si ya existe
                    should_extract = False
                    skipped_count += 1

            if not should_extract:
                continue

            print(f"[{i+1}/{len(links)}] {reason}: {link_data.get('slug') or ext_id}")
            # Evitar pasar 'url' dos veces (una por posición y otra por kwargs)
            extra_params = {k: v for k, v in link_data.items() if k != 'url'}
            details = self.extract_property_details(link_data["url"], **extra_params)
            
            if details:
                # Si es una actualización, reemplazamos la anterior en extracted_data
                if ext_id in local_data:
                    self.extracted_data = [p for p in self.extracted_data if str(p.get("external_id")) != ext_id]
                
                self.extracted_data.append(details)
                local_data[ext_id] = details.get("ingested_at")
                newly_extracted += 1
                
                # if output_path:
                #    self.save_to_json(output_path, client_id=client_id)
            
            # Delay entre extracción
            time.sleep(random.uniform(0.5, 1.5)) # Reducimos delay, ahora somos mas inteligentes
        
        print(f"✅ Proceso finalizado.")
        print(f"   - {skipped_count} Propiedades sin cambios (saltadas).")
        print(f"   - {newly_extracted} Propiedades procesadas (nuevas o actualizadas).")

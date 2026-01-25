import requests
import os
import sys

# Definición de rutas según filesystem_map.md (HOT DATA en NVMe)
TARGET_DIR = "/app/staging/data_raw"
URL = "https://download.geofabrik.de/central-america/costa-rica-latest.osm.pbf"
FILENAME = "costa-rica-latest.osm.pbf"
OUTPUT_PATH = os.path.join(TARGET_DIR, FILENAME)

def download_osm_data():
    """
    Descarga el archivo OSM PBF de Costa Rica y lo guarda en la zona de STAGING/DATA_RAW.
    Usa streaming para eficiencia de memoria.
    """
    # Asegurar que el directorio de destino existe
    if not os.path.exists(TARGET_DIR):
        print(f"Creando directorio de datos crudos: {TARGET_DIR}")
        os.makedirs(TARGET_DIR, exist_ok=True)

    if os.path.exists(OUTPUT_PATH):
        print(f"AVISO: El archivo '{OUTPUT_PATH}' ya existe. Se sobrescribirá.")

    print(f"Iniciando descarga desde: {URL}")
    print(f"Destino: {OUTPUT_PATH}")
    
    try:
        # stream=True es vital para no cargar todo en RAM antes de escribir (Regla de Eficiencia)
        with requests.get(URL, stream=True, timeout=30) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            
            with open(OUTPUT_PATH, 'wb') as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=65536): # 64KB chunks para NVMe
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Feedback visual en consola
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            sys.stdout.write(f"\rProgreso: {percent:.2f}% ({downloaded // (1024*1024)} MB / {total_size // (1024*1024)} MB)")
                            sys.stdout.flush()
                        
        print(f"\n\nÉxito: Archivo guardado correctamente en {OUTPUT_PATH}")

    except Exception as e:
        print(f"\nError durante la descarga: {e}")
        # Si quedó un archivo parcial corrupto, sería ideal manejarlo o reportarlo
        if os.path.exists(OUTPUT_PATH):
            print(f"Revisar integridad en: {OUTPUT_PATH}")

if __name__ == "__main__":
    download_osm_data()
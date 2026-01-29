# 🏘️ ETL PROPERTIES - Pipeline de Ingesta Inmobiliaria

Extracción, normalización y persistencia de propiedades desde múltiples fuentes (WordPress themes y APIs propietarias).

## 🌟 Características Clave
- **Multi-Provider**: Soporta RealHomes, Houzez, WP Residence.
- **Incremental**: Detecta cambios mediante `content_hash` (SHA-256).
- **Metadata Flexible**: Campo `features` JSONB para datos estructurados arbitrarios.
- **Smart Filtering**: Descarta propiedades no publicadas o con precio cero.

## 🚀 Workflow Completo
1. **Ingesta**: `run_ingest.py` ejecuta proveedores configurados en `stage_sources_config`.
2. **Extracción**: Proveedores específicos (`providers/`) normalizan datos de cada tema WordPress.
3. **Persistencia**: `loader_v2.py` inserta/actualiza en `lead_properties` usando UPSERT inteligente.
4. **→ Siguiente**: [ETL-IMAGES](file:///app/.agent/docs/etl_images.md) descarga, optimiza y etiqueta imágenes con Gemini Vision.

## 📂 Componentes
- `run_ingest.py`: Orquestador principal (soporta `--force` para regeneración completa).
- `providers/base_provider.py`: Clase base con normalización de datos.
- `providers/realhomes_provider.py`: Extractor para tema RealHomes.
- `loader_v2.py`: Cargador a PostgreSQL con detección de cambios.

## 🔑 Content Hash
Calcula SHA-256 de:
```
title | price | currency | sqm | lat | lng | features_json
```
Cualquier cambio en estos campos desencadena un UPDATE.

## 📊 Salidas
- **JSON**: `/app/src/ETL_PROPERTIES/output/{SiteName}.json` (staging).
- **DB**: Tabla `lead_properties` (producción).
- **Debug Viewer**: `http://192.168.0.40:8001` para inspección visual.

## 💻 Comandos Útiles

```bash
# Ingesta normal (incremental) para un sitio
python3 run_ingest.py [NombreSitio]
# Ejemplo: python3 run_ingest.py ZonaPlus

# Ingesta FORZADA (ignora fechas, re-descarga todo)
python3 run_ingest.py [NombreSitio] --force
# Ejemplo: python3 run_ingest.py PremierPropiedades --force

# Carga de datos a DB (procesa todos los JSONs en output/)
python3 loader_v2.py
```

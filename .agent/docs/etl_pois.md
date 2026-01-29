# 🗺️ ETL POIS - Contexto Geográfico

Analiza el entorno de la propiedad usando OpenStreetMap (OSM).

## 🚀 Proceso
1. **Descarga**: `download_osm.py` (Mapa base de Costa Rica).
2. **Procesamiento**: `process_pois.py` normaliza marcas (`topbrands.json`) y guarda en `stage_pois_osm`.
3. **Análisis**: `cl_test1.py` genera el "Lead Prep Package" basado en radios de `cl_config_lead_prep.json`.

## 🏆 Jerarquía de Marcas
1. **Anchor Brands**: (Auto Mercado, PriceSmart) - Prioridad máxima.
2. **Priority Brands**: Starbucks, Cargadores EV.
3. **Resto**: POIs genéricos.

## 📊 Salidas
- JSON detallado y GeoJSON para visualización en mapas.

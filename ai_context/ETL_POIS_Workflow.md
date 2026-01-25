# Documentación del Pipeline ETL de POIs y Generación de Lead Prep

Este documento detalla el flujo de trabajo completo, desde la ingesta de datos brutos de OpenStreetMap hasta la generación de análisis inmobiliarios (Lead Prep Package). Sirve como guía para operación manual y como contexto para futuros agentes de IA.

---

## 1. Carga y Procesamiento de POIs (ETL)

El objetivo de este proceso es convertir datos crudos de OSM (formato PBF) en una tabla limpia y enriquecida (`stage_pois_osm`) en PostgreSQL, con marcas normalizadas y puntajes de calidad calculados.

### Pasos Manuales:

1.  **Descargar Datos (Opcional):**
    Si necesitas actualizar el mapa base de Costa Rica (u otra región), ejecuta el descargador.
    ```bash
    python3 /app/src/ETL-POIS/download_osm.py
    ```

2.  **Correr el ETL Principal:**
    Este script lee el PBF, filtra por categorías de interés, normaliza marcas usando `topbrands.json`, y carga la base de datos.
    *   **Comando:**
        ```bash
        python3 /app/src/ETL-POIS/process_pois.py
        ```
    *   **Lo que hace:**
        *   Lee `config_poi_filtering.json` para saber qué tags buscar (amenity, shop, etc.).
        *   Normaliza nombres de marcas (ej: "automercado", "Auto Mercado" -> "Auto Mercado") usando fuzzy matching contra `topbrands.json`.
        *   Calcula un `quality_score` inicial.
        *   Inserta/Actualiza la tabla `stage_pois_osm`.

---

## 2. Archivos de Configuración (Explicación)

El sistema se gobierna por tres archivos JSON clave. Es vital entender qué hace cada uno.

### A. `topbrands.json` (Fuente de Verdad de Marcas)
*   **Propósito:** Diccionario maestro de normalización. Mapea la "Marca Ideal" (como la queremos ver en los reportes) a su "Nombre Real en OSM".
*   **Uso:** El ETL usa esto para limpiar los datos sucios de OSM.
*   **Estructura:**
    ```json
    "Convenience": {
        "Auto Mercado": "Auto Mercado",  <-- Nombre Ideal : Nombre OSM (o substring)
        "Mas x Menos": "Masxmenos"
    }
    ```

### B. `config_poi_filtering.json` (Filtros de Entrada ETL)
*   **Propósito:** Define qué objetos de OSM nos importan durante la extracción inicial. Si no está aquí, no entra a la base de datos.
*   **Contenido:**
    *   `tags_of_interest`: Lista de llaves OSM (amenity, leisure).
    *   `poi_categories`: Agrupaciones lógicas (ej: "Charging_Infrastructure" busca `amenity=charging_station`).

### C. `cl_config_lead_prep.json` (Reglas de Negocio / Reporte)
*   **Propósito:** Configura **cómo se analiza** el entorno para una propiedad específica. Define qué es "cerca", qué es "premium", y qué priorizar.
*   **Claves Importantes:**
    *   `radius_km`: Distancia máxima de búsqueda por categoría.
    *   `priority_brands`: Marcas que suman puntos pero tienen prioridad normal.
    *   `anchor_brands`: **Super-prioridad**. (Ej: Auto Mercado, PriceSmart). Aparecen primero en la lista y definen la zona.
    *   `premium_zone_criteria`: Distancias máximas para considerar una zona como "Premium" (ej: Starbucks a <3km).

---

## 3. Generación de Reportes (Lead Prep)

Una vez que la base de datos está poblada, se pueden generar reportes para cualquier coordenada lat/lon.

### Script Maestro: `cl_test1.py`
Este es el cerebro del análisis inmobiliario.
*   **Entrada:** Latitud, Longitud, Perfil del Lead (opcional).
*   **Proceso:**
    1.  Consulta la BD usando radios configurados en `cl_config_lead_prep.json`.
    2.  Aplica jerarquía: **Anchor > Priority > Otros**.
    3.  Calcula métricas derivadas: `Walkability Score` y `Premium Zone` (Lógica: Grocery Premium + Colegio + (Starbucks O Cargador)).
    4.  Genera "Talking Points" (argumentos de venta en lenguaje natural).
*   **Salida:**
    *   JSON detallado (`lead_prep_package_result.json`).
    *   GeoJSON para mapas (`mapa_propiedad.geojson`).

### Generación de Mapa Visual
El script `create_map.py` toma el GeoJSON generado y crea un HTML interactivo (`mapa_interactivo.html`) para visualización rápida o demos.

---

## 4. Instrucciones para la IA (Future Agents)

**Contexto:**
Eres un ingeniero de datos y backend inmobiliario. Tu trabajo es mantener la precisión de los datos y la relevancia de los insights de venta.

**Reglas de Oro:**
1.  **Nunca inventes datos:** Si OSM no tiene el dato, no existe.
2.  **Respeta la Jerarquía:** Al modificar consultas SQL, siempre mantén el orden: `Anchor Brands` (0) > `Priority Brands` (1) > Resto (2).
3.  **Normalización:** Si encuentras una nueva marca importante mal escrita en los reportes, **no la arregles en el código del reporte**. Agrégala a `topbrands.json` y sugiere re-correr el ETL.
4.  **Carga EV:** La infraestructura de carga es ahora un ciudadano de primera clase (Categoría `Charging_Infrastructure`). Trátala como un factor de "modernidad" equivalente a un café premium.

**Flujo de Debugging Común:**
*   *¿Faltan POIs?* -> Revisa `config_poi_filtering.json` (¿estamos importando ese tag?) y tu consulta Overpass.
*   *¿POI mal clasificado?* -> Revisa el mapeo en `topbrands.json`.
*   *¿Reporte no prioriza bien?* -> Revisa las listas `anchor_brands` en `cl_config_lead_prep.json`.

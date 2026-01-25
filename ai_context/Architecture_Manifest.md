
# Manifiesto de Arquitectura del Sistema (ETL + API)

## Visión General
El sistema es una plataforma modular de procesamiento de propiedades inmobiliarias. Sigue una arquitectura modular horizontal donde cada módulo ETL es independiente pero coordinado, convergiendo todos en la entidad `Propiedad`. La capa de exposición es una API REST (FastAPI).

## Estructura de Directorios (/app/src)

### 1. Módulos ETL (Back-office Processing)
Cada carpeta es un servicio lógico responsable de un aspecto del enriquecimiento de datos.

*   **`/ETL-PROPERTIES`** (Core Ingest)
    *   *Responsabilidad:* Ingesta principal de la propiedad (CRM, CSV, Manual). Crea el registro base en DB.
    *   *Input:* Datos crudos de la propiedad.
    *   *Output:* `property_id` en base de datos.

*   **`/ETL-POIS`** (Contexto Geográfico)
    *   *Responsabilidad:* Análisis del entorno (Cercanía a escuelas, supermercados, carga EV).
    *   *Input:* Lat/Lon de la propiedad + OSM Data (`stage_pois_osm`).
    *   *Output:* Reporte JSON (`property_poi_analyses`) + Mapas GeoJSON/HTML.

*   **`/ETL-DOCS`** (Contexto Documental)
    *   *Responsabilidad:* Procesamiento de documentos legales/financieros (PDFs).
    *   *Proceso:* OCR -> Limpieza -> Chunking -> Vectores.
    *   *Output:* Embeddings en `pgvector`.

*   **`/ETL-IMAGES`** (Contexto Visual)
    *   *Responsabilidad:* Análisis de fotos de la propiedad.
    *   *Proceso:* Vision AI (Etiquetado automático: "Cocina moderna", "Piscina").
    *   *Output:* Etiquetas visuales en DB.

### 2. Orquestación y Comunes
*   **`/orchestrator`**
    *   *Responsabilidad:* Coordinar el flujo. Cuando `ETL-PROPERTIES` termina, dispara eventos para que los otros ETLs trabajen en paralelo sobre el nuevo `property_id`.

*   **`/shared`**
    *   *Responsabilidad:* Código reutilizable para evitar duplicidad.
    *   *Contenido:* Conexión a DB (`database.py`), Loggers standarizados, Utilidades de Hashing.

### 3. Capa de Presentación (API)
*   **`/api`**
    *   *Responsabilidad:* Exponer la funcionalidad al mundo exterior (Frontend, Webhooks).
    *   *Tecnología:* FastAPI.
    *   *Estructura:*
        *   `main.py`: Entrypoint.
        *   `routers/`: Endpoints agrupados (`routers/pois.py`, `routers/docs.py`).
        *   *Nota:* La API **no contiene lógica de negocio pesada**; importa y ejecuta funciones de los módulos ETL.

---

## Flujo de Datos Típico (Pipeline)

1.  **Ingesta:** Cliente POST `/api/properties` -> llama a `ETL-PROPERTIES`.
2.  **Persistencia:** Se crea registro `Property(id=100)`.
3.  **Trigger:** El `orchestrator` detecta nueva propiedad y lanza jobs async:
    *   Job A: `ETL-POIS` analiza el entorno de ID=100.
    *   Job B: `ETL-DOCS` vectoriza los PDFs adjuntos.
    *   Job C: `ETL-IMAGES` etiqueta las fotos subidas.
4.  **Consumo:** Frontend GET `/api/properties/100/full-report` -> Agrega resultados de todas las tablas satélite.

## Dependencias
Ver `/app/src/requirements.txt` para la lista completa de librerías Python instaladas en el entorno (incluyendo geoespaciales y drivers de DB).

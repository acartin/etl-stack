# 🖼️ ETL IMAGES - Arquitectura y Uso

Gestión de la extracción, descarga y optimización de imágenes inmobiliarias.

## 🏗️ Estrategia: "Hot to Cold"
1. **Staging (NVMe)**: Descarga cruda temporal en `/app/staging/ETL_IMAGES/tmp`.
2. **Storage (HDD)**: Conversión a **WebP** y almacenamiento final en `/app/storage/images/`.

##  Workflow Completo
1. **Descarga y Almacenamiento**: `image_loader.py` procesa JSONs de ETL-PROPERTIES, descarga imágenes, convierte a WebP y guarda en `/app/storage/images/{client_id}/properties/{property_id}/{hash}.webp`.
2. **Etiquetado AI**: `image_ai_tagger.py` analiza imágenes con **Gemini Vision** (`gemini-2.0-flash`) para clasificar tipo de habitación, materiales, condición y calidad de foto.
3. **Limpieza**: `image_garbage_collector.py` elimina archivos huérfanos (propiedades/imágenes ya no en DB).

## 📂 Componentes
- `image_loader.py`: Orquestador de descargas por proveedor.
- `providers/`: Lógica específica para RealHomes, Houzez, etc.
- `image_garbage_collector.py`: Asegura consistencia entre Disco y DB.
- `image_ai_tagger.py`: Etiquetado visual con **Gemini Vision** (Cocina, Fachada, etc.).

## 🛠️ Herramientas
- **Debug Viewer**: `/app/src/debug_viewer/` para inspección visual (Puerto 8001).

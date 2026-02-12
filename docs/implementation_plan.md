# Análisis de Migración: Separación de Infraestructura

Este documento analiza los requisitos técnicos para mover los módulos `ETL_DOCS` y `BRAND_CONFIG` a un servidor externo (Web), manteniendo `ETL_IMAGES`, `ETL_POIS` y `ETL_PROPERTIES` en el servidor actual (`prd-media-processor-01`).

## Impacto en Dependencias y Código

Para que la migración sea exitosa sin romper la funcionalidad, se deben abordar los siguientes puntos:

---

### 1. Componentes Compartidos (`src/shared`)
Ambos módulos dependen fuertemente de la carpeta `shared`. Aquí se detallan las funciones y responsabilidades que deben migrarse:

#### `vector_store.py` (Gestión de Conocimiento y Vectores)
*   **`get_embedding(text)`**: Genera el vector numérico usando la API de Google Gemini (`text-embedding-004`). Crucial para la búsqueda semántica.
*   **`upsert_document(doc)`**: Realiza la lógica de "Insertar o Actualizar". Incluye la verificación de duplicados mediante Hash (SHA-256) antes de vectorizar.
*   **`register_document_in_db()`**: Crea el registro maestro en la tabla `ai_knowledge_documents` (Postgres).
*   **`update_sync_status()`**: Actualiza el estado del documento (`PENDING`, `SYNCED`, `FAILED`).
*   **`list_documents(client_id)`**: Recupera la lista de documentos para mostrar en el frontend.
*   **`delete_document()`**: Elimina vectores y registros vinculados.

#### `file_manager.py` (Gestión de Archivos Físicos)
*   **`save_upload(file_bytes, filename, client_id)`**: Guarda físicamente el PDF en la ruta de almacenamiento configurada.
*   **`_get_client_dir(client_id)`**: Calcula dinámicamente la ruta del cliente basada en la variable `PATH_STORAGE`.
*   **`check_file_exists()`**: Evita sobreescrituras accidentales.
*   **`delete_document()` / `delete_client_folder()`**: Limpieza física de archivos en disco.

#### `schemas.py` (Modelos de Calidad y Datos)
*   Define clases Pydantic esenciales: `CanonicalDocument`, `CanonicalMetadata`, `SemanticItem`, y Enums de estado (`IngestStatus`, `AccessLevel`). Sin estos, el procesamiento de datos fallará por inconsistencia de tipos.

**Acción requerida**: Se debe replicar la carpeta `src/shared` en el nuevo servidor o refactorizar estos componentes para que sean librerías independientes.

### 2. Conectividad de Base de Datos
*   **Situación actual**: Los archivos `vector_store.py` y `BRAND_CONFIG/database.py` apuntan a `192.168.0.31` (IP interna).
*   **Acción requerida**: Si el nuevo servidor está en "la web", no podrá ver esa IP. Se requiere:
    *   Un túnel VPN o VPC Peering entre el servidor web y la red local.
    *   O exponer la base de datos de forma segura (vía proxy o endpoint seguro).

### 3. Estrategia de Almacenamiento (Storage)
Este es el punto más crítico:
*   **ETL_DOCS**: Lee y guarda PDFs en `/app/data/storage/documents/`.
*   **BRAND_CONFIG**: Guarda logos y banners procesados en `/app/data/storage/images/`.
*   **Acción requerida**: El servidor nuevo no tiene acceso al disco duro físico de 4TB del servidor actual. Opciones:
    *   **Sincronización**: Usar `rsync` o herramientas de sincronización de archivos.
    *   **Almacenamiento en la Nube**: Migrar ambos módulos para que usen S3 (AWS) o Google Cloud Storage en lugar de rutas locales.
    *   **NFS/Mount**: Montar el almacenamiento del servidor actual en el nuevo servidor.

### 4. Redis y Workers (Cola de Tareas)
*   **ETL_DOCS** encola tareas pesadas (OCR) en Redis.
*   **Acción requerida**: ¿El Worker seguirá corriendo en el servidor actual o se moverá también?
    *   Si el Worker se mueve: Necesita acceso a las mismas librerías de sistema (`tesseract-ocr`, `poppler-utils`).
    *   Si el Worker se queda: El servidor web debe poder conectarse al Redis del servidor actual.

### 5. API de Google Gemini
*   Ambos módulos requieren la `GOOGLE_API_KEY`.
*   **Acción requerida**: Replicar el archivo `.env` con las llaves necesarias en el nuevo entorno.

## Resumen de Archivos a Mover
Para que los módulos funcionen en el nuevo servidor, se deben copiar:
1.  Todo el directorio `src/ETL_DOCS/`.
2.  Todo el directorio `src/BRAND_CONFIG/`.
3.  Todo el directorio `src/shared/`.
4.  El archivo `src/.env`.
5.  El archivo de definición del API (probablemente `src/api/`).

---

## Plan de Verificación (Simulado)

Para validar la migración sin haberla hecho todavía, se recomienda:
1.  **Test de Conectividad**: Desde el nuevo entorno, verificar `ping` o `nc` hacia el host de la DB.
2.  **Mocks de Storage**: Crear una carpeta temporal que emule `/app/data/storage` para verificar que el código no truene por falta de rutas.
3.  **Dry-run del Worker**: Levantar un proceso de `rq worker` en el nuevo entorno y enviarle una tarea de prueba.

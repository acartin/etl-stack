
# 🏗️ Módulo ETL-DOCS: Base de Conocimiento Documental

Este módulo implementa el pipeline de ingesta, procesamiento y vectorización de documentos (PDFs) para la Base de Conocimiento del Agente.

## 🌟 Características Clave
*   **Asíncrono y Escalable (Redis Queue):** La API responde <100ms y un Worker dedicado procesa los archivos pesados.
*   **Híbrido (Texto/OCR):** Usa `pypdf` para extracción rápida y `Tesseract OCR` como fallback automático si el PDF son imágenes escaneadas.
*   **Idempotente (Hashing SHA-256):** Detecta duplicados a nivel de contenido. No procesa ni cobra embeddings por documentos repetidos.
*   **Vectorización SOTA:** Integrado con Google Gemini (`text-embedding-004`) para embeddings de alta calidad (768d).
*   **Persistencia Robusta:** Archivos en disco (`/storage`) + Metadatos/Vectores en Postgres (`pgvector`).

---

## 📂 Estructura de Archivos (/app/src)

### 1. Núcleo Compartido (`/shared`)
Servicios transversales utilizados por todos los ETLs.

*   `schemas.py`: Modelos Pydantic unificados (`CanonicalDocument`).
*   `file_manager.py`: Abstracción del disco físico. Guarda en `/app/storage/documents/{client_id}/`.
*   `vector_store.py`: **El Guardián**.
    *   Conecta con Postgres (DB `agentic`).
    *   Genera embeddings vía Google Gemini.
    *   Maneja Upserts inteligentes (Insert/Update) y control de duplicados (Unique Hash).

### 2. Procesamiento (`/ETL_DOCS`)
Lógica de negocio específica de documentos.

*   `processor.py`: Orquestador puro.
    *   `_extract_text_from_pdf()`: Lógica dual Pypdf/OCR.
    *   `process_document()`: Extrae -> Crea Canonical -> Llama a VectorStore.
*   `worker_task.py`: Wrapper aislado para ser serializado por RQ (Redis Queue).
    *   Maneja excepciones y logging del Worker.

### 3. API & Colas
*   `/api/routers/docs.py`: Endpoints FastAPI.
    *   `POST /upload`: Guarda archivo -> Encola Job en Redis -> Retorna `job_id`.
    *   `GET /jobs/{id}`: Polling de estado.
    *   `DELETE /...`: Borrado síncrono.
*   `worker_service.py`: Entrypoint del proceso Worker. Escucha la cola `etl_queue`.

---

## 📡 API Reference

### 1. Subir Documento
**POST** `/documents/upload`
*   **Body (Multipart):**
    *   `file`: (Binary PDF)
    *   `client_id`: (UUID)
*   **Respuesta (202 Accepted):**
    ```json
    {
        "status": "QUEUED",
        "job_id": "job_doc_d3b0...",
        "queue_position": 0
    }
    ```

### 2. Consultar Estado
**GET** `/documents/jobs/{job_id}`
*   **Respuesta:**
    ```json
    {
        "status": "finished",
        "result": {
            "status": "SYNCED",
            "hash": "..."
        }
    }
    ```

### 3. Borrar Documento
**DELETE** `/documents/{client_id}/{content_id}`
*   Elimina vectores de la DB. (Pendiente: limpieza física sincronizada).

### 4. Borrar Cliente (Purga)
**DELETE** `/documents/client/{client_id}`
*   Elimina TODOS los vectores y la carpeta física del cliente.

---

## ⚙️ Configuración (.env)
Este módulo depende de las siguientes variables configuradas en `/app/src/.env`:

```ini
# Base de Datos
DB_HOST=192.168.0.31
DB_NAME=agentic

# Inteligencia Artificial
GOOGLE_API_KEY=AIzaSy...
EMBEDDING_MODEL=models/text-embedding-004
EMBEDDING_DIMENSIONS=768

# Rutas
PATH_STORAGE="/app/storage"
```

## 🛠️ Comandos de Operación

**Iniciar API:**
```bash
python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

**Iniciar Worker:**
```bash
python3 -m src.worker_service
```

**Dependencias del Sistema:**
*   `redis-server` (Cola)
*   `tesseract-ocr` (Motor OCR)
*   `poppler-utils` (Renderizado PDF)

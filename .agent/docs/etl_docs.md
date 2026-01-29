# 🏗️ Módulo ETL-DOCS: Base de Conocimiento Documental

Este módulo implementa el pipeline de ingesta, procesamiento y vectorización de documentos (PDFs) para la Base de Conocimiento del Agente.

## 🌟 Características Clave
*   **Asíncrono (Redis Queue)**: Worker procesa archivos pesados.
*   **Híbrido (Texto/OCR)**: Fallback automático a Tesseract si el PDF es imagen.
*   **Idempotente (SHA-256)**: Evita duplicados de contenido.
*   **Vectorización**: Google Gemini (`text-embedding-004`).

## 📂 Estructura
- `/shared/file_manager.py`: Almacenamiento físico en `/app/storage/documents/`.
- `/shared/vector_store.py`: Gestión de embeddings y Postgres/pgvector.
- `/ETL_DOCS/processor.py`: Lógica de extracción Texto/OCR.

## 📡 API
- `POST /documents/upload`: Encola job.
- `GET /documents/jobs/{id}`: Estado del procesamiento.

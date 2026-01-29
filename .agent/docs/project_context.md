# 🧠 Project Brain: Real Estate ETL Engine

This file is the **Source of Truth** for the project. Read it before any action to ensure consistency and prevent context loss.

## 🏗️ Infrastructure (LXC Container #401)
- **Environment**: Debian 12 (Linux).
- **Hostname**: `prd-media-processor-01`
- **Resources**: 4 Cores, 8GB RAM, 1GB Swap.
- **Network**: `192.168.0.40`
- **Setup Script**: [/app/setup_lxc_401.sh](file:///app/setup_lxc_401.sh)

## 📂 Filesystem & Storage Strategy
The system uses a hybrid storage architecture. **Respect paths strictly.**

| Path | Hardware | Purpose |
| :--- | :--- | :--- |
| `/app/src` | System | Python scripts, logic, and `.env`. |
| `/app/staging` | **NVMe** | **HOT DATA**: Downloads, temporary processing, unzipping. |
| `/app/storage` | **HDD (4TB)** | **COLD DATA**: Final datasets (Parquet), archived images/PDFs. |

### Staging Subfolders (NVMe)
- `/app/staging/data_raw`: Incoming raw files (CSV/JSON/Excel).
- `/app/staging/documents_in`: PDFs waiting for OCR.
- `/app/staging/images_raw`: Original high-res photos.
- `/app/staging/temp_work`: Workspace for `.zip` or `.pbf` extraction.

### Storage Subfolders (HDD)
- `/app/storage/datasets_clean`: Processed data (Parquet/DuckDB).
- `/app/storage/images_web`: Optimized WebP images for frontend.
- `/app/storage/documents_arch`: Historical archive of original documents.

## 🐍 Software Stack & State
- **Language**: Python 3 (installed via `apt` and `pip` with `--break-system-packages`).
- **Web**: FastAPI + Uvicorn (REST API).
- **Data**: DuckDB, Pandas, SQLAlchemy, Postgres (Client).
- **Geo**: GeoPandas, OSMnx, Shapely, GDAL/Geos.
- **AI/Vision**: Google GenAI (Gemini API), Pytesseract (OCR).
- **Queues**: Redis + RQ (Redis Queue).
- **Secrets**: Located at [/app/src/.env](file:///app/src/.env). 
  - ⚠️ **MANDATORY**: Always use `cat` in the terminal to read this file due to permissions.

## 🚀 Modular Pipelines
We are building a modular enrichment system for properties. For deep technical details, refer to the specific module docs:

- **[ETL-PROPERTIES]**: Core ingestion and DB creation. (Docs pending)
- **[ETL-POIS]**: [.agent/docs/etl_pois.md](file:///app/.agent/docs/etl_pois.md).
- **[ETL-DOCS]**: [.agent/docs/etl_docs.md](file:///app/.agent/docs/etl_docs.md).
- **[ETL-IMAGES]**: [.agent/docs/etl_images.md](file:///app/.agent/docs/etl_images.md).

## ⚙️ DevOps & Services
The platform runs as persistent services using `systemd`.

| Service | Description | Command to Check |
| :--- | :--- | :--- |
| `etl-api` | FastAPI Web Server (Port 8000) | `systemctl status etl-api` |
| `etl-worker` | Redis/RQ Task Processor | `systemctl status etl-worker` |

### Management Commands
- **Restart All**: `systemctl restart etl-api etl-worker`
- **View API Logs**: `journalctl -u etl-api -n 50 -f`
- **View Worker Logs**: `journalctl -u etl-worker -n 50 -f`

## 🛠️ Operations
- **Working Directory**: Usually `/app/src`.
- **Database**: PostgreSQL (main storage) + DuckDB/Parquet (large datasets).
- **Execution**: Run scripts via `python3 [script_path]`.

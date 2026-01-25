# 🗺️ Mapa de Infraestructura (LXC Container)

El código se ejecuta en un entorno Linux (Debian 12) con una arquitectura de almacenamiento híbrida (NVMe + HDD). Las rutas son absolutas.

## 📂 Raíz del Proyecto: `/app`

### 1. 🧠 CÓDIGO Y CONFIGURACIÓN
**Ruta:** `/app/src`
* Aquí viven todos los scripts `.py`.
* Aquí vive el archivo `.env` (credenciales).
* **Regla:** Todo script debe ejecutarse asumiendo que el *working directory* puede variar, por lo que siempre se deben usar rutas absolutas a `staging` o `storage`.

---

### 2. 🔥 STAGING (NVMe - Disco Rápido)
**Ruta:** `/app/staging`
**Hardware:** Virtual Disk en NVMe (Alta velocidad I/O).
**Uso:** Ingesta, descompresión, procesamiento temporal, descargas de OSM/Imágenes.

* `/app/staging/data_raw`      -> CSVs, Excels y JSONs crudos entrantes.
* `/app/staging/documents_in`  -> PDFs legales/contratos esperando OCR.
* `/app/staging/images_raw`    -> Fotos de propiedades sin procesar (alta res).
* `/app/staging/temp_work`     -> Zona sucia para descomprimir .zip o .pbf temporales.

---

### 3. ❄️ STORAGE (HDD - Disco Masivo 4TB)
**Ruta:** `/app/storage`
**Hardware:** Bind Mount a HDD Físico (Lento pero enorme).
**Uso:** Archivo final, Datasets limpios (Parquet/SQL), Histórico.

* `/app/storage/datasets_clean` -> Datos procesados listos para consumo (Parquet/DuckDB).
* `/app/storage/documents_arch` -> Archivo histórico de PDFs originales.
* `/app/storage/images_web`     -> Imágenes optimizadas/redimensionadas para frontend.
* `/app/storage/property-images`-> (Legacy) Archivo histórico de imágenes.

---

### ⚠️ Reglas de Movimiento de Datos
1.  **Ingesta:** Todo entra por **STAGING** (NVMe).
2.  **Proceso:** El ETL "cocina" los datos en STAGING.
3.  **Persistencia:** Una vez procesado, el resultado final se mueve a **STORAGE** (HDD) y lo temporal se borra.
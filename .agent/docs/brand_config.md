# 🎨 Módulo BRAND-CONFIG: Configurador de Marca

Este módulo gestiona la identidad visual de los clientes, centralizando logos, banners, colores y tipografías para su uso en bots, landing pages y sitios web.

## 🌟 Características Clave
*   **Gestión de Activos**: Subida, validación, redimensionado inteligente y conversión automática a **WebP**.
*   **Cálculo de Contraste**: Determinación automática de color de texto (blanco/negro) según luminosidad del color primario.
*   **Inyección CSS**: Endpoint dinámico que genera variables CSS (`:root`) consumibles desde el frontend.
*   **Garbage Collector**: Identificación y eliminación de imágenes huérfanas en disco.

## 📂 Estructura
- `/BRAND_CONFIG/models.py`: Tabla SQL `leads_brand_configs` (colores, fuentes, rutas de archivos).
- `/BRAND_CONFIG/service.py`: Lógica con `Pillow` para resize y conversión a WebP.
- `/BRAND_CONFIG/utils.py`: Algoritmo de luminancia para contraste.
- `/BRAND_CONFIG/garbage_collector.py`: Script de mantenimiento.

## 📡 API
- `GET /brand-config/{client_id}`: Obtener configuración.
- `PUT /brand-config/{client_id}`: Guardar colores/fuentes.
- `POST /brand-config/{client_id}/assets/{asset_type}`: Subir logo/banner.
- `GET /brand-config/{client_id}/css`: Obtener CSS dinámico.

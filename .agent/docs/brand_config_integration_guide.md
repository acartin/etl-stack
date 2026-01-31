# 🎨 Brand Configurator Integration Guide

Current Context: You are working on the Frontend (VM `www`). You need to consume the **Brand Configurator API** hosted on the Backend Service.

## 📡 API Configuration
**Base URL**: `http://192.168.0.40:8000`

## 1. Dynamic CSS Injection (Critical)
Instead of hardcoding colors, inject the client's brand variables dynamically.

**Endpoint**: `GET /brand-config/{client_id}/css?project=default`
**Usage**: Add this `<link>` tag in your HTML `<head>`:

```html
<link rel="stylesheet" href="http://192.168.0.40:8000/brand-config/<CLIENT_ID>/css?project=main_tower">
```

**Variables Available**:
This will make the following CSS variables available globally:
- `--brand-primary`: Main brand color.
- `--text-on-primary`: `#FFFFFF` or `#1A1A1A` (Auto-calculated for contrast).
- `--font-heading`: Google Font for headers.
- `--font-body`: Google Font for body text.
- `--radius-base`: Border radius preference.

## 2. Getting Config & Assets (JSON)
To get logo URLs and raw values.

**Endpoint**: `GET /brand-config/{client_id}?project=default`
**Response** (Complete Object):
```json
{
  "client_id": "uuid...",
  "project": "default",
  "id": "uuid...",
  
  "primary_color": "#FF5733",
  "secondary_color": "#333333",
  "surface_color": "#F5F5F5",
  "text_on_primary": "#FFFFFF", 
  
  "font_heading_name": "Inter",
  "font_heading_url": "https://fonts.googleapis.com/css2?family=Inter...",
  "font_body_name": "Roboto",
  "font_body_url": "https://fonts.googleapis.com/css2?family=Roboto...",
  
  "border_radius": "4px",
  "box_shadow_style": "0 4px 6px -1px rgb(0 0 0 / 0.1)",
  
  "logo_header_path": "/app/storage/images/.../branding/default/identity/logo_header.webp",
  "logo_square_path": "/app/storage/images/.../branding/default/identity/logo_square.webp",
  "banner_main_path": "/app/storage/images/.../branding/default/banners/banner_main.webp",
  "banner_promo_path": "/app/storage/images/.../branding/default/banners/banner_promo.webp",
  
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

## 3. List All Configurations for a Client
To get all brand configurations (all projects) for a specific client.

**Endpoint**: `GET /brand-config/{client_id}/list`
**Response** (Array):
```json
[
  {
    "client_id": "uuid...",
    "project": "default",
    "id": "uuid...",
    "primary_color": "#FF5733",
    ...
  },
  {
    "client_id": "uuid...",
    "project": "main_tower",
    "id": "uuid...",
    "primary_color": "#0066CC",
    ...
  }
]
```

## 4. Uploading Assets
**Endpoint**: `POST /brand-config/{client_id}/assets/{asset_type}?project=default`
**Asset Types**: `logo_header`, `logo_square`, `banner_main`, `banner_promo`.
**Method**: `multipart/form-data` with key `file`.

## 4. Updating Configuration (JSON)
To save colors, fonts, and styles. This is decoupled from asset uploads.
**Endpoint**: `PUT /brand-config/{client_id}?project=default`
**Method**: `PUT` (Upsert logic: creates or updates)
**Body (JSON)** - All fields are optional but recommended:
```json
{
  "primary_color": "#FF5733",
  "secondary_color": "#333333",
  "surface_color": "#F5F5F5",
  
  "font_heading_name": "Inter",
  "font_heading_url": "https://fonts.googleapis...",
  "font_body_name": "Roboto",
  "font_body_url": "https://fonts.googleapis...",
  
  "border_radius": "4px",        // Matches var --radius-base
  "box_shadow_style": "none"     // Matches var --box-shadow-card
}
```

## 5. Deleting Config
**Endpoint**: `DELETE /brand-config/{client_id}?project=default`
**Effect**: Removes DB config AND deletes all physical files immediately.

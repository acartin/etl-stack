from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, status, Response
from sqlalchemy.orm import Session
from uuid import UUID

from .database import get_db
from .schemas import BrandConfigCreate, BrandConfigUpdate, BrandConfigResponse
from .service import BrandService

router = APIRouter(
    prefix="/brand-config",
    tags=["Brand Config"]
)

@router.get("/{client_id}/list", response_model=list[BrandConfigResponse])
def list_brand_configs(client_id: UUID, db: Session = Depends(get_db)):
    """
    Returns all brand configurations for a client (all projects).
    """
    configs = BrandService.list_configs(db, client_id)
    if not configs:
        return []  # Return empty list if no configs found
    return configs

@router.get("/{client_id}", response_model=BrandConfigResponse)
def get_brand_config(client_id: UUID, project: str = "default", db: Session = Depends(get_db)):
    config = BrandService.get_config(db, client_id, project)
    if not config:
        # Return empty config if not found, or raise 404? 
        # For multi-project, maybe 404 is appropriate if that specific project isn't configured.
        raise HTTPException(status_code=404, detail=f"Brand config not found for project '{project}'")
    return config

@router.put("/{client_id}", response_model=BrandConfigResponse)
def update_brand_config(client_id: UUID, config_in: BrandConfigUpdate, project: str = "default", db: Session = Depends(get_db)):
    return BrandService.create_or_update_config(db, client_id, config_in, project)

@router.post("/{client_id}/assets/{asset_type}")
async def upload_brand_asset(
    client_id: UUID, 
    asset_type: str, 
    file: UploadFile = File(...), 
    project: str = "default",
    db: Session = Depends(get_db)
):
    """
    Asset Types: 'logo_header', 'logo_square', 'banner_main', 'banner_promo'
    """
    return await BrandService.save_asset(db, client_id, asset_type, file, project)

@router.get("/{client_id}/css")
def get_brand_css(client_id: UUID, project: str = "default", db: Session = Depends(get_db)):
    config = BrandService.get_config(db, client_id, project)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
        
    css = f"""
/* Generated CSS for Client {client_id} (Project: {project}) */
:root {{
    --brand-primary: {config.primary_color};
    --brand-secondary: {config.secondary_color};
    --brand-surface: {config.surface_color};
    
    /* Calculated */
    --text-on-primary: {config.text_on_primary};
    --brand-primary-dark: color-mix(in srgb, {config.primary_color}, black 20%);
    
    /* Typography */
    --font-heading: '{config.font_heading_name}', sans-serif;
    --font-body: '{config.font_body_name}', sans-serif;
    
    /* Geometry */
    --radius-base: {config.border_radius};
    --box-shadow-card: {config.box_shadow_style};
}}

body {{
    font-family: var(--font-body);
    background-color: var(--brand-surface);
}}

h1, h2, h3 {{
    font-family: var(--font-heading);
    color: var(--brand-primary);
}}
"""
    return Response(content=css, media_type="text/css")

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand_config(client_id: UUID, project: str = "default", db: Session = Depends(get_db)):
    """
    Deletes the brand configuration and all associated assets for a client/project.
    """
    success = BrandService.delete_config(db, client_id, project)
    if not success:
        raise HTTPException(status_code=404, detail="Brand config not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

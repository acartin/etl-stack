from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class BrandConfigBase(BaseModel):
    project: Optional[str] = "default"
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    surface_color: Optional[str] = None
    font_heading_url: Optional[str] = None
    font_heading_name: Optional[str] = None
    font_body_url: Optional[str] = None
    font_body_name: Optional[str] = None
    border_radius: Optional[str] = None
    box_shadow_style: Optional[str] = None
    # We don't accept base64 directly in update usually, but can populate it
    logo_header_base64: Optional[str] = None
    logo_square_base64: Optional[str] = None

class BrandConfigCreate(BrandConfigBase):
    pass

class BrandConfigUpdate(BrandConfigBase):
    pass

class BrandConfigResponse(BrandConfigBase):
    client_id: UUID
    logo_header_path: Optional[str] = None
    logo_square_path: Optional[str] = None
    banner_main_path: Optional[str] = None
    banner_promo_path: Optional[str] = None
    text_on_primary: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class AssetUploadResponse(BaseModel):
    filename: str
    path: str
    url_path: str # web accessible path maybe?
    width: int
    height: int
    format: str

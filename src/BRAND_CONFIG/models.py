from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from .database import Base

class BrandConfig(Base):
    __tablename__ = "lead_brand_configs"
    __table_args__ = (UniqueConstraint('client_id', 'project', name='uq_client_project'),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), index=True, nullable=False)
    project = Column(String, default="default", nullable=False)
    
    # 1. Identidad Cromatica
    primary_color = Column(String(7)) # HEX
    secondary_color = Column(String(7))
    surface_color = Column(String(7))
    
    # 2. Identidad Tipografica
    font_heading_url = Column(Text)
    font_heading_name = Column(String)
    font_body_url = Column(Text)
    font_body_name = Column(String)
    
    # 3. Identidad Geometrica
    border_radius = Column(String) # '0px', '4px', '20px'
    box_shadow_style = Column(String)
    
    # 4. Activos (Base64 is kept for compatibility/caching, but we mainly use paths now)
    logo_header_base64 = Column(Text, nullable=True) # Optional
    logo_square_base64 = Column(Text, nullable=True)
    
    # Paths for stored files
    logo_header_path = Column(String, nullable=True)
    logo_square_path = Column(String, nullable=True)
    banner_main_path = Column(String, nullable=True)
    banner_promo_path = Column(String, nullable=True)

    # 5. Contraste (Calculated)
    text_on_primary = Column(String(7))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

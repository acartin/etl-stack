import os
import shutil
import base64
from pathlib import Path
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException
from PIL import Image
from io import BytesIO

from .models import BrandConfig
from .schemas import BrandConfigCreate, BrandConfigUpdate
from .utils import calculate_text_contrast

STORAGE_ROOT = Path(os.getenv("PATH_STORAGE", "/app/storage"))

class BrandService:
    
    @staticmethod
    def _get_client_images_dir(client_id: UUID, project: str = "default") -> Path:
        """
        Retorna el directorio raíz de imágenes del cliente para un proyecto específico.
        Estructura: /app/storage/images/{client_id}/branding/{project}/
        """
        return STORAGE_ROOT / "images" / str(client_id) / "branding" / project

    @staticmethod
    def get_config(db: Session, client_id: UUID, project: str = "default") -> BrandConfig:
        return db.query(BrandConfig).filter(
            BrandConfig.client_id == client_id,
            BrandConfig.project == project
        ).first()

    @staticmethod
    def list_configs(db: Session, client_id: UUID) -> list[BrandConfig]:
        """
        Returns all brand configurations for a given client (all projects).
        """
        return db.query(BrandConfig).filter(
            BrandConfig.client_id == client_id
        ).order_by(BrandConfig.project).all()

    @classmethod
    def create_or_update_config(cls, db: Session, client_id: UUID, config_in: BrandConfigUpdate, project: str = "default") -> BrandConfig:
        config = cls.get_config(db, client_id, project)
        if not config:
            config = BrandConfig(client_id=client_id, project=project)
            db.add(config)
        
        # Update fields
        data = config_in.dict(exclude_unset=True)
        # Ensure we don't overwrite project if it was passed in body (though query param rules)
        if "project" in data:
            del data["project"]
            
        for key, value in data.items():
            setattr(config, key, value)
            
        # Calculate contrast if primary_color changed
        if config.primary_color:
            config.text_on_primary = calculate_text_contrast(config.primary_color)
            
        db.commit()
        db.refresh(config)
        return config

    @classmethod
    async def save_asset(cls, db: Session, client_id: UUID, asset_type: str, file: UploadFile, project: str = "default"):
        """
        Saves logic with Project support.
        """
        valid_assets = {
            "logo_header": {"path": "identity", "resize": "h80"},
            "logo_square": {"path": "identity", "resize": "500x500"},
            "banner_main": {"path": "banners", "resize": "w1600"},
            "banner_promo": {"path": "banners", "resize": None}
        }
        
        if asset_type not in valid_assets:
            raise HTTPException(status_code=400, detail=f"Invalid asset_type. Must be one of {list(valid_assets.keys())}")
        
        rule = valid_assets[asset_type]
        # Use new dir structure
        base_dir = cls._get_client_images_dir(client_id, project) / rule["path"]
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Read image
        contents = await file.read()
        try:
            img = Image.open(BytesIO(contents))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image file")
            
        # Processing
        if rule["resize"] == "h80":
            aspect = img.width / img.height
            new_h = 80
            new_w = int(new_h * aspect)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
        elif rule["resize"] == "500x500":
            img = img.resize((500, 500), Image.Resampling.LANCZOS)
            
        elif rule["resize"] == "w1600":
            if img.width > 1600:
                aspect = img.height / img.width
                new_w = 1600
                new_h = int(new_w * aspect)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Save as WebP
        filename = f"{asset_type}.webp"
        save_path = base_dir / filename
        
        img.save(save_path, "WEBP", quality=85)
        
        # Encode Base64
        buffered = BytesIO()
        img.save(buffered, format="WEBP")
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # Update DB
        current_update = BrandConfigUpdate() # empty update
        config = cls.create_or_update_config(db, client_id, current_update, project)
        
        # Update specific fields
        if asset_type == "logo_header":
            config.logo_header_path = str(save_path)
            config.logo_header_base64 = img_base64
        elif asset_type == "logo_square":
            config.logo_square_path = str(save_path)
            config.logo_square_base64 = img_base64
        elif asset_type == "banner_main":
            config.banner_main_path = str(save_path)
        elif asset_type == "banner_promo":
            config.banner_promo_path = str(save_path)
            
        db.commit()
        db.refresh(config)
        
        return {
            "filename": filename,
            "path": str(save_path),
            "width": img.width,
            "height": img.height,
            "project": project
        }

    @classmethod
    def delete_config(cls, db: Session, client_id: UUID, project: str = "default") -> bool:
        """
        Deletes the brand configuration for a specific project.
        """
        # 1. Delete physical files (Project Folder)
        # Ahora es seguro borrar todo el directorio del proyecto dentro de 'branding'
        client_dir = cls._get_client_images_dir(client_id, project)
        if client_dir.exists():
            try:
                shutil.rmtree(client_dir)
                print(f"Deleted branding project folder: {client_dir}")
            except Exception as e:
                print(f"Error deleting directory {client_dir}: {e}")

        # 2. Delete from DB
        config = cls.get_config(db, client_id, project)
        if config:
            db.delete(config)
            db.commit()
            return True
        return False

import os
from pathlib import Path
from sqlalchemy.orm import Session
from src.BRAND_CONFIG.database import SessionLocal
from src.BRAND_CONFIG.models import BrandConfig

STORAGE_ROOT = Path(os.getenv("PATH_STORAGE", "/app/storage"))
IMAGES_ROOT = STORAGE_ROOT / "images"

def garbage_collect_images():
    print("Starting Garbage Collection for Brand Images...")
    db = SessionLocal()
    try:
        # Get all referenced paths
        configs = db.query(BrandConfig).all()
        referenced_paths = set()
        for c in configs:
            if c.logo_header_path: referenced_paths.add(Path(c.logo_header_path).resolve())
            if c.logo_square_path: referenced_paths.add(Path(c.logo_square_path).resolve())
            if c.banner_main_path: referenced_paths.add(Path(c.banner_main_path).resolve())
            if c.banner_promo_path: referenced_paths.add(Path(c.banner_promo_path).resolve())
        
        # Traverse directory bottom-up to clean files then empty dirs
        deleted_count = 0
        deleted_dirs_count = 0
        
        if IMAGES_ROOT.exists():
            for root, dirs, files in os.walk(IMAGES_ROOT, topdown=False):
                # 1. Clean Files
                for file in files:
                    file_path = Path(root) / file
                    try:
                        resolved_path = file_path.resolve()
                        if resolved_path not in referenced_paths:
                            print(f"Deleting orphan file: {file_path}")
                            os.remove(file_path)
                            deleted_count += 1
                    except Exception as e:
                        print(f"Error checking file {file_path}: {e}")
                
                # 2. Clean Directory if empty
                # Check actual content on disk after file deletion
                if not os.listdir(root):
                    # Don't delete the root images folder itself, only subfolders
                    if Path(root).resolve() != IMAGES_ROOT.resolve():
                        try:
                            print(f"Deleting empty directory: {root}")
                            os.rmdir(root)
                            deleted_dirs_count += 1
                        except Exception as e:
                            print(f"Error deleting dir {root}: {e}")
                        
        print(f"Garbage Collection Complete. Deleted {deleted_count} files and {deleted_dirs_count} folders.")
            
    finally:
        db.close()

if __name__ == "__main__":
    garbage_collect_images()

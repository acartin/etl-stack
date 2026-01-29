from src.BRAND_CONFIG.database import engine, Base
from src.BRAND_CONFIG.models import BrandConfig

def init_db():
    print("Creating tables for BRAND_CONFIG...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()

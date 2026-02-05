
import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

# DB Config
DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
engine = create_engine(DB_URL)

print("--- Table List ---")
insp = inspect(engine)
tables = insp.get_table_names()
print(tables)

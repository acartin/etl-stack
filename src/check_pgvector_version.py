import os
import sys
import psycopg2
from dotenv import load_dotenv

# Force load .env
try:
    load_dotenv("/app/src/.env", override=True)
except Exception as e:
    print(f"Error loading .env: {e}", file=sys.stderr)

db_host = os.getenv("DB_HOST", "192.168.0.31")
db_name = os.getenv("DB_NAME", "agentic")
db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")

try:
    print(f"Connecting into {db_host}...")
    conn = psycopg2.connect(
        host=db_host,
        dbname=db_name,
        user=db_user,
        password=db_pass
    )
    with conn.cursor() as cur:
        # Check pgvector version
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
        row = cur.fetchone()
        if row:
            print(f"pgvector version: {row[0]}")
        else:
            print("pgvector extension NOT FOUND")
            
    conn.close()
except Exception as e:
    print(f"DB Check failed: {e}", file=sys.stderr)

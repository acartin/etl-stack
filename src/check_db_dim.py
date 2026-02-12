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
    conn = psycopg2.connect(
        host=db_host,
        dbname=db_name,
        user=db_user,
        password=db_pass
    )
    with conn.cursor() as cur:
        # Check column type for 'embedding' in 'ai_vectors'
        cur.execute("""
            SELECT data_type, udt_name, character_maximum_length
            FROM information_schema.columns 
            WHERE table_name = 'ai_vectors' AND column_name = 'embedding';
        """)
        row = cur.fetchone()
        print(f"Column Info: {row}", file=sys.stderr)
        
        # Also try to check pgvector specific dimension if possible
        cur.execute("""
            SELECT atttypmod 
            FROM pg_attribute 
            WHERE attrelid = 'ai_vectors'::regclass AND attname = 'embedding';
        """)
        row_dim = cur.fetchone()
        print(f"Attribute mod (dim): {row_dim}", file=sys.stderr)

    conn.close()
except Exception as e:
    print(f"DB Check failed: {e}", file=sys.stderr)

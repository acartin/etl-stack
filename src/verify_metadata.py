import psycopg2
import os
import json
from dotenv import load_dotenv

load_dotenv("/app/src/.env")

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

def check_metadata():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT content_id, metadata 
        FROM ai_vectors 
        WHERE client_id = '64f357a0-98eb-44f1-9f41-6e615ed26180'
        ORDER BY created_at DESC
        LIMIT 3
    """)
    
    results = cursor.fetchall()
    
    print(f"Found {len(results)} records for client 64f357a0-98eb-44f1-9f41-6e615ed26180\n")
    
    for content_id, metadata in results:
        print(f"Content ID: {content_id}")
        if metadata:
            print(f"Metadata:")
            print(f"  - embedding_model: {metadata.get('embedding_model', 'NOT FOUND')}")
            print(f"  - embedding_dimension: {metadata.get('embedding_dimension', 'NOT FOUND')}")
            print(f"  - category: {metadata.get('category', 'NOT FOUND')}")
        else:
            print("  NO METADATA FOUND")
        print()
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_metadata()

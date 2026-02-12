import os
import sys
import pypdf
import uuid
from typing import List
from dotenv import load_dotenv

# Force load .env
try:
    load_dotenv("/app/src/.env", override=True)
except Exception as e:
    print(f"Error loading .env: {e}", file=sys.stderr)

# Add src to path
sys.path.append("/app")

try:
    from src.shared.vector_store import VectorStore
    from src.shared.schemas import CanonicalDocument, CanonicalMetadata, SourceType, AccessLevel
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

PDF_PATH = "/app/data/storage/documents/64f357a0-98eb-44f1-9f41-6e615ed26180/Eliana faq.pdf"
CLIENT_ID = uuid.UUID("64f357a0-98eb-44f1-9f41-6e615ed26180") # Assuming client ID from path

def test_pdf_insertion():
    print(f"Testing PDF Insertion: {PDF_PATH}")
    
    if not os.path.exists(PDF_PATH):
        print("File not found!", file=sys.stderr)
        return

    # 1. Initialize VectorStore
    try:
        vs = VectorStore()
        print("VectorStore initialized.")
    except Exception as e:
        print(f"VectorStore init failed: {e}", file=sys.stderr)
        return

    # 2. Process PDF
    try:
        reader = pypdf.PdfReader(PDF_PATH)
        emb_model = os.getenv('EMBEDDING_MODEL', 'unknown')
        
        print(f"Processing {len(reader.pages)} pages...")
        
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text: continue
            
            chunk_content = text.strip()
            chunk_id = f"test_pdf_page_{i+1}_{uuid.uuid4().hex[:6]}"
            chunk_hash = vs.calculate_hash(chunk_content)
            
            # --- METADATA WITH VERSION & DIMS ---
            meta = CanonicalMetadata(
                client_id=CLIENT_ID,
                category="test_faq",
                access_level=AccessLevel.PRIVATE,
                # Extra fields (supported now via Config.extra = "allow")
                embedding_model=emb_model,
                embedding_dimension=3072, # We know this from previous test
                test_run="true"
            )
            
            doc = CanonicalDocument(
                content_id=chunk_id,
                source=SourceType.PDF_UPLOAD,
                title=f"Eliana FAQ - Test Page {i+1}",
                body_content=chunk_content,
                hash=chunk_hash,
                metadata=meta
            )
            
            print(f"Upserting Page {i+1} (ID: {chunk_id})...")
            vs.upsert_document(doc)
            print(f"  -> Success!")
            
    except Exception as e:
        print(f"Insertion Failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    test_pdf_insertion()

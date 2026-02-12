import os
import sys
import pypdf
from typing import List
from dotenv import load_dotenv

# Force load .env
try:
    load_dotenv("/app/src/.env", override=True)
except Exception as e:
    print(f"Error loading .env: {e}", file=sys.stderr)

# Add src to path to import shared modules
sys.path.append("/app")

try:
    from src.shared.vector_store import VectorStore
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

PDF_PATH = "/app/data/storage/documents/64f357a0-98eb-44f1-9f41-6e615ed26180/Eliana faq.pdf"

def test_pdf_embedding():
    print(f"Testing PDF: {PDF_PATH}")
    
    if not os.path.exists(PDF_PATH):
        print("File not found!", file=sys.stderr)
        return

    # 1. Extract Text
    text = ""
    try:
        reader = pypdf.PdfReader(PDF_PATH)
        print(f"Pages: {len(reader.pages)}")
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
                print(f"Page {i+1} extracted {len(page_text)} chars.")
            else:
                print(f"Page {i+1} empty.")
    except Exception as e:
        print(f"Error reading PDF: {e}", file=sys.stderr)
        return

    if not text.strip():
        print("No text extracted from PDF.", file=sys.stderr)
        return

    print(f"Total extracted text length: {len(text)}")

    # 3. Generate Embeddings for ALL pages
    print(f"\n--- Generating Embeddings for {len(reader.pages)} pages ---")
    
    try:
        vs = VectorStore()
        print("VectorStore initialized.")
    except Exception as e:
        print(f"VectorStore init failed: {e}", file=sys.stderr)
        return

    for i, page in enumerate(reader.pages):
        text_content = page.extract_text()
        if not text_content:
            print(f"Skipping Page {i+1} (empty)")
            continue
            
        print(f"Processing Page {i+1} ({len(text_content)} chars)...")
        try:
            vector = vs.get_embedding(text_content)
            print(f"  -> SUCCESS! Vector generated. Dim: {len(vector)}")
        except Exception as e:
            print(f"  -> FAILED: {e}")

if __name__ == "__main__":
    test_pdf_embedding()

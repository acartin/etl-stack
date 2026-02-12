import os
import sys
from dotenv import load_dotenv

# Force load .env
load_dotenv("/app/src/.env", override=True)
sys.path.append("/app")

try:
    from src.shared.vector_store import VectorStore
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test_new_sdk():
    print("Testing google-genai SDK migration...")
    print(f"Embedding Model: {os.getenv('EMBEDDING_MODEL')}")
    
    try:
        vs = VectorStore()
        print("VectorStore initialized successfully.")
        
        # Test embedding generation
        test_text = "This is a test document for the new SDK migration."
        print(f"\nGenerating embedding for test text ({len(test_text)} chars)...")
        
        vector = vs.get_embedding(test_text)
        print(f"SUCCESS! Vector generated.")
        print(f"Dimensions: {len(vector)}")
        print(f"First 5 values: {vector[:5]}")
        
        if len(vector) != 3072:
            print(f"WARNING: Expected 3072 dimensions, got {len(vector)}")
            sys.exit(1)
            
        print("\n✓ google-genai SDK migration successful!")
        
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_new_sdk()

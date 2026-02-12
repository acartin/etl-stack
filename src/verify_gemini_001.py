import os
import sys
import google.generativeai as genai
from dotenv import load_dotenv

# Force load .env
try:
    load_dotenv("/app/src/.env", override=True)
except Exception as e:
    print(f"Error loading .env: {e}", file=sys.stderr)

api_key = os.getenv("GOOGLE_API_KEY")
model = os.getenv("EMBEDDING_MODEL")

print(f"Model to test: {model}", file=sys.stderr)

if not api_key:
    print("API KEY MISSING", file=sys.stderr)
    sys.exit(1)

try:
    genai.configure(api_key=api_key)
    res = genai.embed_content(
        model=model,
        content="Test embedding",
        task_type="retrieval_document"
    )
    print(f"Success! Embedding generated for {model}. Length: {len(res['embedding'])}", file=sys.stderr)
except Exception as e:
    print(f"Embedding failed for {model}: {e}", file=sys.stderr)
    sys.exit(1)

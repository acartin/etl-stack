
import requests
import uuid
import os

# Configuración
API_URL = "http://localhost:8000/documents/upload"
CLIENT_ID = "019b4872-51f6-72d3-84c9-45183ff700d0" # Cliente Existente
FILENAME = "test_duplicate.pdf"

# Crear PDF dummy limpio
with open(FILENAME, "wb") as f:
    f.write(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")

def upload_file(step_name):
    print(f"\n--- {step_name} ---")
    with open(FILENAME, "rb") as f:
        files = {"file": (FILENAME, f, "application/pdf")}
        data = {
            "client_id": CLIENT_ID,
            "access_level": "shared",
            "category": "Test"
        }
        try:
            response = requests.post(API_URL, files=files, data=data)
            print(f"Status Code: {response.status_code}")
            try:
                print(f"Response: {response.json()}")
            except:
                print(f"Raw Text: {response.text}")
            return response.status_code
        except Exception as e:
            print(f"Error conectando: {e}")
            return None

# 1. Primer Upload (Debería ser 202)
code1 = upload_file("Intento 1 (Subida Limpia)")

if code1 == 202:
    print("✅ Primer upload exitoso.")
else:
    print("❌ Falló el primer upload. Abortando.")
    exit(1)

# 2. Segundo Upload (Debería ser 409)
code2 = upload_file("Intento 2 (Duplicado Intencional)")

if code2 == 409:
    print("✅ ÉXITO TOTAL: El sistema detectó el duplicado correctamente (409).")
elif code2 == 500:
    print("❌ FALLO CRÍTICO: El sistema devolvió 500 en lugar de 409.")
else:
    print(f"⚠️ Resultado inesperado: {code2}")

# Limpieza
if os.path.exists(FILENAME):
    os.remove(FILENAME)

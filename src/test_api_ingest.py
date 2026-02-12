import requests
import time
import sys
import os

API_URL = "http://localhost:8000"
CLIENT_ID = "64f357a0-98eb-44f1-9f41-6e615ed26180"
# Use a renamed file to avoid "File exists" error if previous one wasn't cleaned
PDF_SOURCE = "/tmp/Eliana_test_upload.pdf" 
UPLOAD_FILENAME = "Eliana_FAQ_Test_v2.pdf" # Unique name for this test

def test_api_flow():
    print(f"--- Starting End-to-End API Test ---")
    print(f"Target: {API_URL}")
    print(f"Client: {CLIENT_ID}")
    
    if not os.path.exists(PDF_SOURCE):
        print(f"Error: Source file not found at {PDF_SOURCE}")
        sys.exit(1)

    # 1. Upload Document
    print(f"\n1. Uploading document as '{UPLOAD_FILENAME}'...")
    try:
        with open(PDF_SOURCE, 'rb') as f:
            # We send the file with a specific filename
            files = {'file': (UPLOAD_FILENAME, f, 'application/pdf')}
            data = {
                'client_id': CLIENT_ID,
                'category': 'test_api_flow',
                'visibility': 'private'
            }
            response = requests.post(f"{API_URL}/documents/upload", files=files, data=data)
            
        if response.status_code != 202:
            print(f"Upload Failed: {response.status_code} - {response.text}")
            sys.exit(1)
            
        result = response.json()
        job_id = result['job_id']
        content_id = result['content_id']
        print(f"  -> Upload Accepted!")
        print(f"  -> Job ID: {job_id}")
        print(f"  -> Content ID: {content_id}")
        
    except Exception as e:
        print(f"Upload Error: {e}")
        sys.exit(1)

    # 2. Poll Job Status
    print(f"\n2. Polling Job Status...")
    start_time = time.time()
    while time.time() - start_time < 60: # 1 minute timeout
        try:
            status_resp = requests.get(f"{API_URL}/documents/jobs/{job_id}")
            if status_resp.status_code != 200:
                print(f"Job Status Error: {status_resp.text}")
                break
                
            job_data = status_resp.json()
            status = job_data['status']
            print(f"  -> Status: {status}")
            
            if status == 'finished':
                print(f"  -> SUCCESS! Job finished.")
                print(f"  -> Result: {job_data.get('result')}")
                break
            elif status == 'failed':
                print(f"  -> FAILED! Job failed.")
                print(f"  -> Error: {job_data.get('error')}")
                sys.exit(1)
                
            time.sleep(2)
        except Exception as e:
            print(f"Polling Error: {e}")
            break
    else:
        print("Timeout waiting for job completion.")
        sys.exit(1)

if __name__ == "__main__":
    test_api_flow()

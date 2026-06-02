import json, os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2 import service_account

load_dotenv()

sa_raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
sa_json = json.loads(sa_raw)

print(f"Service account email: {sa_json.get('client_email')}")
print(f"Project ID: {sa_json.get('project_id')}")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = service_account.Credentials.from_service_account_info(sa_json, scopes=SCOPES)

drive = build("drive", "v3", credentials=creds, cache_discovery=False)

print("\n--- Files in service account Drive ---")
try:
    files = drive.files().list(fields="files(id, name, mimeType, size)").execute().get("files", [])
    if not files:
        print("No files found")
    for f in files:
        print(f"  {f['name']} | {f['id']} | {f.get('size', 'N/A')} bytes")
except Exception as e:
    print(f"FAILED: {e}")

print("\n--- About (storage quota) ---")
try:
    about = drive.about().get(fields="storageQuota").execute()
    q = about.get("storageQuota", {})
    print(f"  Usage: {q.get('usage', '?')} bytes")
    print(f"  Limit: {q.get('limit', 'unlimited')}")
except Exception as e:
    print(f"FAILED: {e}")

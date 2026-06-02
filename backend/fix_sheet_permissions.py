"""One-time script: adds service account as writer to all existing sheets in the DB."""
import json, os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials as OAuthCredentials
from database import SessionLocal
from models.client import Client

load_dotenv()

client_id     = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
refresh_token = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN")
sa_raw        = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
sa_json       = json.loads(sa_raw) if sa_raw else {}
sa_email      = sa_json.get("client_email", "")

creds = OAuthCredentials(
    token=None,
    refresh_token=refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=client_id,
    client_secret=client_secret,
    scopes=["https://www.googleapis.com/auth/drive"],
)
drive = build("drive", "v3", credentials=creds, cache_discovery=False)

db = SessionLocal()
clients = db.query(Client).filter(Client.sheets_id != None).all()

for client in clients:
    print(f"\n{client.business_name} → sheet: {client.sheets_id}")
    try:
        drive.permissions().create(
            fileId=client.sheets_id,
            body={"type": "user", "role": "writer", "emailAddress": sa_email},
            sendNotificationEmail=False,
        ).execute()
        print(f"  ✅ Added {sa_email} as writer")
    except Exception as e:
        print(f"  ❌ {e}")

db.close()

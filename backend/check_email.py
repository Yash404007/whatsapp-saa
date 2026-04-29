from database import SessionLocal
from models.client import Client

db = SessionLocal()
client = db.query(Client).first()
print("Service account email:", client.google_credentials.get('client_email'))
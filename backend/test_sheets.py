from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal
from models.client import Client

db = SessionLocal()
client = db.query(Client).first()

print(f"Business: {client.business_name}")
print(f"use_sheets: {client.use_sheets}")
print(f"sheets_id: {client.sheets_id}")
print(f"google_credentials: {'✅ Set' if client.google_credentials else '❌ Not set'}")

if client.google_credentials and client.sheets_id:
    from services.sheets_service import add_lead_to_sheets
    add_lead_to_sheets(
        business_name=client.business_name,
        phone="919321898637",
        collected_data={
            "email": "test@gmail.com",
            "service_type": "Website Design",
            "budget": "10k-15k",
            "timeline": "1 month"
        },
        google_credentials=client.google_credentials,
        sheet_id=client.sheets_id,
    )
    print("✅ Sheets test done — check your Google Sheet!")
else:
    print("❌ Missing sheets_id or google_credentials")
    print("Go to /docs and update client with sheets_id")
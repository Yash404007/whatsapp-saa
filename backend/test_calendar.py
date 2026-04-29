from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal
from models.client import Client

db = SessionLocal()
client = db.query(Client).first()

print(f"Business: {client.business_name}")
print(f"calendar_id: {client.calendar_id}")
print(f"google_credentials: {'✅ Set' if client.google_credentials else '❌ Not set'}")

if client.google_credentials:
    from googleapiclient.discovery import build
    from google.oauth2 import service_account

    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    creds = service_account.Credentials.from_service_account_info(
        client.google_credentials, scopes=SCOPES
    )
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    # Try to access the calendar directly by ID
    if client.calendar_id:
        try:
            cal = service.calendars().get(calendarId=client.calendar_id).execute()
            print(f"✅ Calendar found: {cal['summary']}")

            # Try creating a test event
            from datetime import datetime, timedelta
            start = datetime.utcnow() + timedelta(hours=1)
            end = start + timedelta(minutes=30)

            event = service.events().insert(
                calendarId=client.calendar_id,
                body={
                    "summary": "Test Appointment",
                    "description": "Test from WhatsApp SaaS",
                    "start": {"dateTime": start.isoformat() + "Z"},
                    "end": {"dateTime": end.isoformat() + "Z"},
                },
            ).execute()
            print(f"✅ Test event created: {event.get('htmlLink')}")
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print("❌ No calendar_id set in database")
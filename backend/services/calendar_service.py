from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from google.oauth2 import service_account
from loguru import logger

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_credentials(google_credentials: dict):
    return service_account.Credentials.from_service_account_info(
        google_credentials, scopes=SCOPES
    )


def create_calendar_event(
    business_name: str,
    calendar_id: str,
    google_credentials: dict,
    collected_data: dict,
    phone: str,
):
    """Create a Google Calendar event from collected lead data."""
    try:
        creds = _get_credentials(google_credentials)
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        # Try to get date and time from collected data
        date_str = collected_data.get("date") or collected_data.get("appointment_date")
        time_str = collected_data.get("time") or collected_data.get("appointment_time")
        name = collected_data.get("name", phone)
        reason = collected_data.get("reason") or collected_data.get("service_type") or "Appointment"

        if date_str and time_str:
            # Parse date and time
            try:
                start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            except Exception:
                start_dt = datetime.now(timezone.utc) + timedelta(days=1)
        else:
            # Default to tomorrow at 10am
            start_dt = datetime.now(timezone.utc).replace(
                hour=10, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)

        end_dt = start_dt + timedelta(minutes=30)

        # Build description from all collected fields
        description_lines = [f"📱 Phone: {phone}", f"🏢 Business: {business_name}", ""]
        for key, value in collected_data.items():
            description_lines.append(f"• {key.replace('_', ' ').title()}: {value}")
        description_lines.append("\nBooked via WhatsApp Bot")
        description = "\n".join(description_lines)

        event = service.events().insert(
            calendarId=calendar_id,
            sendUpdates="none",
            body={
                "summary": f"📋 {name} — {reason}",
                "description": description,
                "start": {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": "Asia/Kolkata"
                },
                "end": {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": "Asia/Kolkata"
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 30},
                    ],
                },
            },
        ).execute()

        logger.info(f"📅 Calendar event created for {name} | {business_name}")
        return event.get("htmlLink", "")

    except Exception as e:
        logger.error(f"❌ Calendar error: {str(e)}")
        return None
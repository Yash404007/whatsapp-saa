from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account
from loguru import logger

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_credentials(google_credentials: dict):
    return service_account.Credentials.from_service_account_info(
        google_credentials, scopes=SCOPES
    )


def add_lead_to_sheets(
    business_name: str,
    phone: str,
    collected_data: dict,
    google_credentials: dict,
    sheet_id: str,
):
    """Add lead to Google Sheets using direct sheet ID."""
    try:
        creds = _get_credentials(google_credentials)
        sheets_svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

        if not sheet_id:
            raise Exception("No sheet ID provided.")

        # Add headers if sheet is empty
        existing = sheets_svc.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="A1:Z1",
        ).execute()

        if not existing.get("values"):
            headers = ["Phone"] + [k.replace("_", " ").title() for k in collected_data.keys()] + ["Submitted At"]
            sheets_svc.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="A1",
                valueInputOption="USER_ENTERED",
                body={"values": [headers]},
            ).execute()
            logger.info("📊 Headers added to sheet")

        # Build row
        timestamp = datetime.now().strftime("%d %b %Y %I:%M %p")
        row = [phone] + [str(v) for v in collected_data.values()] + [timestamp]

        # Append row
        sheets_svc.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="A:Z",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()

        logger.info(f"📊 Lead added to sheets for {business_name}")

    except Exception as e:
        logger.error(f"❌ Sheets error: {str(e)}")
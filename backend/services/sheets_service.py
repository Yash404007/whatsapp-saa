import time
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account
from loguru import logger

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_credentials(google_credentials: dict):
    creds = service_account.Credentials.from_service_account_info(
        google_credentials, scopes=SCOPES
    )
    return creds


def add_lead_to_sheets(
    business_name: str,
    phone: str,
    collected_data: dict,
    google_credentials: dict,
):
    """Add lead to Google Sheets. Creates sheet if it doesn't exist."""
    try:
        creds = _get_credentials(google_credentials)
        sheets_svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        drive_svc  = build("drive",  "v3", credentials=creds, cache_discovery=False)

        title = f"{business_name} - Leads"
        safe_title = title.replace("'", "\\'")

        # Search for existing sheet
        results = drive_svc.files().list(
            q=f"name='{safe_title}' and mimeType='application/vnd.google-apps.spreadsheet'",
            fields="files(id, name)",
        ).execute()

        if results.get("files"):
            sheet_id = results["files"][0]["id"]
        else:
            # Create new sheet
            spreadsheet = sheets_svc.spreadsheets().create(body={
                "properties": {"title": title},
                "sheets": [{
                    "properties": {"title": "Leads", "sheetId": 0},
                }]
            }).execute()
            sheet_id = spreadsheet["spreadsheetId"]
            logger.info(f"📊 Created new sheet: {title}")

        # Build row
        timestamp = datetime.now().strftime("%d %b %Y %I:%M %p")
        row = [phone] + [str(v) for v in collected_data.values()] + [timestamp]

        sheets_svc.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Leads!A:Z",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()

        logger.info(f"📊 Lead added to sheets for {business_name}")

    except Exception as e:
        logger.error(f"❌ Sheets error: {str(e)}")
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


def _build_chat_summary(history: list) -> str:
    """Build a readable chat summary from history."""
    lines = []
    for msg in history:
        role = "User" if msg.get("role") == "user" else "Bot"
        text = msg.get("parts", [{}])[0].get("text", "")
        if text:
            lines.append(f"{role}: {text[:100]}")
    return " | ".join(lines[-10:])  # Last 10 messages


def add_lead_to_sheets(
    business_name: str,
    phone: str,
    collected_data: dict,
    google_credentials: dict,
    sheet_id: str,
    chat_history: list = None,
):
    """Add lead to Google Sheets with chat summary."""
    try:
        creds = _get_credentials(google_credentials)
        sheets_svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

        if not sheet_id:
            raise Exception("No sheet ID provided.")

        # Check if headers exist
        existing = sheets_svc.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="A1:Z1",
        ).execute()

        if not existing.get("values"):
            headers = (
                ["Phone"]
                + [k.replace("_", " ").title() for k in collected_data.keys()]
                + ["Chat Summary", "Submitted At"]
            )
            sheets_svc.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="A1",
                valueInputOption="USER_ENTERED",
                body={"values": [headers]},
            ).execute()
            logger.info("📊 Headers added to sheet")

        # Build chat summary
        summary = _build_chat_summary(chat_history or [])

        # Build row
        timestamp = datetime.now().strftime("%d %b %Y %I:%M %p")
        row = (
            [phone]
            + [str(v) for v in collected_data.values()]
            + [summary, timestamp]
        )

        sheets_svc.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="A:Z",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()

        logger.info(f"📊 Lead + chat summary saved for {business_name}")

    except Exception as e:
        logger.error(f"❌ Sheets error: {str(e)}")
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account
from loguru import logger

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── Fixed column order in the sheet ──────────────────────────────────────────
# Change this list to reorder or rename columns in your sheet.
SHEET_HEADERS = [
    "Business",
    "Phone",
    "Name",
    "Email",
    "Date",
    "Service",
    "Qualification Notes",
    "Conversation Summary",
    "Submitted At",
]

# Internal bot-engine keys that should NEVER appear in the sheet
_INTERNAL_KEYS = {
    "_qualify_step",
    "_qualify_turns",
    "_qa_0",
    "_qa_1",
    "_qa_2",
    "_qa_3",
}

# Maps collected_data keys → sheet column names
_FIELD_MAP = {
    "name": "Name",
    "email": "Email",
    "date": "Date",
    "phone": "Phone",           # in case phone is also in collected_data
    "service_type": "Service",
    "preferred_time": "Date",   # alias
    "time": "Date",             # alias
}


def _get_credentials(google_credentials: dict):
    return service_account.Credentials.from_service_account_info(
        google_credentials, scopes=SCOPES
    )


def _build_qualification_notes(collected_data: dict) -> str:
    """
    Pull the service-qualification answers (_qa_0, _qa_1 …) out of
    collected_data and return them as a short readable string.

    Example output:
        "Q1: E-commerce site | Q2: Need it in 3 weeks"
    """
    notes = []
    for i in range(10):
        answer = collected_data.get(f"_qa_{i}")
        if not answer:
            break
        notes.append(f"Q{i + 1}: {answer.strip()}")
    return " | ".join(notes) if notes else "—"


def _build_conversation_summary(history: list, collected_data: dict) -> str:
    """
    Build a concise human-readable summary of what the conversation was about.

    Strategy:
    - Use the selected service as the anchor
    - Add qualification answers for context
    - Do NOT dump raw chat messages

    Example output:
        "Interested in AI Integration — wants to add a chatbot for customer
         support and reduce response time."
    """
    service = collected_data.get("service_type", "")

    # Pull qualification answers
    qa_parts = []
    for i in range(10):
        answer = collected_data.get(f"_qa_{i}")
        if not answer:
            break
        qa_parts.append(answer.strip())

    if service and qa_parts:
        detail = " — " + "; ".join(qa_parts)
        return f"Interested in {service}{detail}"
    elif service:
        return f"Interested in {service}"
    elif qa_parts:
        return "; ".join(qa_parts)

    # Fallback: pull only the first user message that looks like intent
    # (skip greeting resets, one-word replies)
    for msg in history:
        if msg.get("role") != "user":
            continue
        text = (msg.get("parts") or [{}])[0].get("text", "").strip()
        if len(text) > 15:          # ignore "hi", "1", "yes" etc.
            return text[:120]

    return "—"


def add_lead_to_sheets(
    business_name: str,
    phone: str,
    collected_data: dict,
    google_credentials: dict,
    sheet_id: str,
    chat_history: list = None,
):
    """
    Append one lead row to Google Sheets.

    Columns are FIXED (see SHEET_HEADERS) so the sheet stays consistent
    regardless of which fields each client collects.
    Internal bot-engine keys (_qualify_step, _qa_0 …) are never written.
    """
    try:
        creds = _get_credentials(google_credentials)
        sheets_svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

        if not sheet_id:
            raise ValueError("No sheet ID provided.")

        # ── Ensure header row exists ──────────────────────────────────────
        existing = (
            sheets_svc.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range="A1:Z1")
            .execute()
        )

        if not existing.get("values"):
            sheets_svc.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="A1",
                valueInputOption="USER_ENTERED",
                body={"values": [SHEET_HEADERS]},
            ).execute()
            logger.info("📊 Sheet headers created")

        # ── Build the row in fixed column order ───────────────────────────
        timestamp = datetime.now().strftime("%d %b %Y %I:%M %p")

        qualification_notes = _build_qualification_notes(collected_data)
        conversation_summary = _build_conversation_summary(
            chat_history or [], collected_data
        )

        # Map collected_data to fixed columns
        data = {h: "" for h in SHEET_HEADERS}   # default every column to ""
        data["Business"]              = business_name or "—"
        data["Phone"]                 = phone or "—"
        data["Name"]                  = collected_data.get("name", "—")
        data["Email"]                 = collected_data.get("email", "—")
        data["Service"]               = collected_data.get("service_type", "—")
        data["Qualification Notes"]   = qualification_notes
        data["Conversation Summary"]  = conversation_summary
        data["Submitted At"]          = timestamp

        # Date: prefer explicit "date" field, fall back to preferred_time / time
        data["Date"] = (
            collected_data.get("date")
            or collected_data.get("preferred_time")
            or collected_data.get("time")
            or "—"
        )

        row = [data[h] for h in SHEET_HEADERS]

        sheets_svc.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="A:Z",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()

        logger.info(f"📊 Lead saved for {business_name} | {phone}")

    except Exception as e:
        logger.error(f"❌ Sheets error: {e}")
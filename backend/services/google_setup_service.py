from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials
from loguru import logger

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
SHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _sa_creds(sa_json: dict, scopes: list):
    return service_account.Credentials.from_service_account_info(sa_json, scopes=scopes)


def _oauth_creds(client_id: str, client_secret: str, refresh_token: str):
    return OAuthCredentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SHEET_SCOPES,
    )


def setup_google_for_client(
    business_name: str,
    share_emails: list[str],
    sa_json: dict,
    oauth: dict = None,          # {"client_id": ..., "client_secret": ..., "refresh_token": ...}
) -> dict:
    """
    Creates a Google Sheet (via OAuth) + Google Calendar (via service account) for one client.
    Shares both with every email in share_emails (writer access).
    Returns {"sheets_id": ..., "calendar_id": ...} — keys absent on failure.
    """
    result = {}

    # ── Google Sheet (OAuth — admin Gmail owns it, no service-account Drive quota needed) ──
    try:
        if not oauth or not oauth.get("refresh_token"):
            raise ValueError("OAuth credentials not configured — add GOOGLE_OAUTH_* to .env")

        sheet_creds = _oauth_creds(oauth["client_id"], oauth["client_secret"], oauth["refresh_token"])
        sheets_svc = build("sheets", "v4", credentials=sheet_creds, cache_discovery=False)
        drive_svc  = build("drive",  "v3", credentials=sheet_creds, cache_discovery=False)

        sheet = sheets_svc.spreadsheets().create(body={
            "properties": {"title": f"{business_name} — Leads"},
        }).execute()
        sheet_id = sheet["spreadsheetId"]

        # Also share with the service account so the bot can write rows to the sheet
        sa_email = sa_json.get("client_email", "") if sa_json else ""
        sheet_share = list(share_emails)
        if sa_email and sa_email not in sheet_share:
            sheet_share.append(sa_email)

        for email in sheet_share:
            drive_svc.permissions().create(
                fileId=sheet_id,
                body={"type": "user", "role": "writer", "emailAddress": email},
                sendNotificationEmail=False,
            ).execute()
            logger.info(f"📊 Sheet shared with {email}")

        result["sheets_id"] = sheet_id
        logger.success(f"📊 Sheet created for '{business_name}': {sheet_id}")

    except Exception as e:
        logger.error(f"❌ Sheet creation failed for '{business_name}': {e}")

    # ── Google Calendar (service account — no Drive storage needed) ──────────────
    try:
        cal_svc = build("calendar", "v3", credentials=_sa_creds(sa_json, CALENDAR_SCOPES), cache_discovery=False)

        cal = cal_svc.calendars().insert(body={
            "summary": f"{business_name} — Appointments",
            "timeZone": "Asia/Kolkata",
        }).execute()
        calendar_id = cal["id"]

        for email in share_emails:
            cal_svc.acl().insert(
                calendarId=calendar_id,
                body={"role": "owner", "scope": {"type": "user", "value": email}},
            ).execute()
            logger.info(f"📅 Calendar shared with {email}")

        result["calendar_id"] = calendar_id
        logger.success(f"📅 Calendar created for '{business_name}': {calendar_id}")

    except Exception as e:
        logger.error(f"❌ Calendar creation failed for '{business_name}': {e}")

    return result

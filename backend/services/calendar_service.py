from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re
from googleapiclient.discovery import build
from google.oauth2 import service_account
from loguru import logger

SCOPES = ["https://www.googleapis.com/auth/calendar"]

IST = ZoneInfo("Asia/Kolkata")

# Internal bot keys — never shown in calendar description
_INTERNAL_KEYS = {
    "_qualify_step", "_qualify_turns",
    "_qa_0", "_qa_1", "_qa_2", "_qa_3",
}

# ── Date format patterns to try in order ─────────────────────────────────────
_DATE_FORMATS = [
    "%d %B %Y",       # 15 January 2025
    "%d %b %Y",       # 15 Jan 2025
    "%B %d %Y",       # January 15 2025
    "%b %d %Y",       # Jan 15 2025
    "%d/%m/%Y",       # 15/01/2025
    "%Y-%m-%d",       # 2025-01-15
    "%d-%m-%Y",       # 15-01-2025
    "%d %B",          # 15 January  (no year → current year assumed)
    "%d %b",          # 15 Jan
    "%B %d",          # January 15
    "%b %d",          # Jan 15
    "%d/%m",          # 15/01
]

_TIME_FORMATS = [
    "%I:%M %p",       # 2:30 PM
    "%I %p",          # 2 PM
    "%H:%M",          # 14:30
    "%I:%M%p",        # 2:30PM (no space)
    "%I%p",           # 2PM
]

# Weekday name → weekday index (Monday=0)
_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}

# Relative day keywords
_RELATIVE = {
    "today": 0, "tonight": 0,
    "tomorrow": 1, "tmrw": 1, "tmr": 1,
    "day after tomorrow": 2,
}


def _get_credentials(google_credentials: dict):
    return service_account.Credentials.from_service_account_info(
        google_credentials, scopes=SCOPES
    )


# ─────────────────────────────────────────────────────────────────────────────
# DATE PARSING
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date(raw: str) -> datetime | None:
    """
    Parse a natural-language date string into a datetime (date part only).
    Returns a datetime at midnight IST, or None if unparseable.

    Handles:
    - "Monday", "next Friday"
    - "tomorrow", "today", "day after tomorrow"
    - "15th Jan", "15 January", "Jan 15", "15/01/2025"
    - "next week" → following Monday
    - "this week" → coming weekday
    """
    if not raw:
        return None

    now = datetime.now(IST)
    text = raw.lower().strip()

    # Strip ordinal suffixes: 15th → 15, 1st → 1, 2nd → 2, 3rd → 3
    text_clean = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", text)

    # ── Relative keywords ─────────────────────────────────────────────────
    for keyword, days_ahead in _RELATIVE.items():
        if keyword in text_clean:
            return (now + timedelta(days=days_ahead)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

    # ── "next week" ───────────────────────────────────────────────────────
    if "next week" in text_clean:
        # Next Monday
        days_until_monday = (7 - now.weekday()) % 7 or 7
        return (now + timedelta(days=days_until_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    # ── Weekday names ─────────────────────────────────────────────────────
    is_next = "next" in text_clean
    for name, target_wd in _WEEKDAYS.items():
        if name in text_clean:
            current_wd = now.weekday()
            diff = (target_wd - current_wd) % 7
            if diff == 0:
                diff = 7   # same weekday → next week
            elif is_next:
                diff = diff if diff > 0 else diff + 7
                # "next Monday" when today is Tuesday → 6 days ahead
                if diff <= 0:
                    diff += 7
            return (now + timedelta(days=diff)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

    # ── Explicit date formats ─────────────────────────────────────────────
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text_clean.strip(), fmt)
            # If no year in format, use current year (or next if date passed)
            if "%Y" not in fmt:
                parsed = parsed.replace(year=now.year)
                if parsed.date() < now.date():
                    parsed = parsed.replace(year=now.year + 1)
            return parsed.replace(tzinfo=IST, hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            continue

    # ── Partial match: find a day number + optional month in the string ───
    # e.g. "around 20th" or "after 15 jan"
    match = re.search(
        r"(\d{1,2})\s*(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
        r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)?",
        text_clean,
    )
    if match:
        day = int(match.group(1))
        month_raw = match.group(2)
        if month_raw:
            try:
                parsed = datetime.strptime(f"{day} {month_raw[:3].title()}", "%d %b")
                parsed = parsed.replace(year=now.year, tzinfo=IST,
                                        hour=0, minute=0, second=0, microsecond=0)
                if parsed.date() < now.date():
                    parsed = parsed.replace(year=now.year + 1)
                return parsed
            except ValueError:
                pass
        else:
            # Day-only: pick nearest upcoming occurrence of that day
            candidate = now.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
            if candidate.date() < now.date():
                # Try next month
                if now.month == 12:
                    candidate = candidate.replace(year=now.year + 1, month=1)
                else:
                    candidate = candidate.replace(month=now.month + 1)
            return candidate

    return None


def _parse_time(raw: str) -> tuple[int, int] | None:
    """
    Parse a natural-language time string into (hour, minute) in 24h.
    Returns None if unparseable — caller defaults to 10:00.

    Handles:
    - "2:30 PM", "2 PM", "14:30", "morning", "afternoon", "evening"
    - "10am", "3pm", "11:00 AM"
    """
    if not raw:
        return None

    text = raw.lower().strip()

    # Vague time-of-day words
    vague = {
        "morning": (10, 0),
        "afternoon": (14, 0),
        "evening": (17, 0),
        "night": (19, 0),
        "noon": (12, 0),
        "midnight": (0, 0),
    }
    for word, hm in vague.items():
        if word in text:
            return hm

    # Normalise: "10am" → "10 am", "3:30pm" → "3:30 pm"
    text = re.sub(r"(\d)(am|pm)", r"\1 \2", text)
    text = re.sub(r"(\d)\s*(am|pm)", r"\1 \2", text).strip()

    for fmt in _TIME_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            return (parsed.hour, parsed.minute)
        except ValueError:
            continue

    # Last attempt: bare number like "10" or "3" → assume AM if <8, else AM/PM heuristic
    match = re.fullmatch(r"(\d{1,2})", text.strip())
    if match:
        h = int(match.group(1))
        if 1 <= h <= 7:
            h += 12   # treat 1–7 as PM
        return (h, 0)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# DESCRIPTION BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def _build_description(phone: str, business_name: str, collected_data: dict) -> str:
    """Build a clean event description from collected lead data."""
    label_map = {
        "name": "Name",
        "email": "Email",
        "service_type": "Service",
        "date": "Requested Date",
        "time": "Requested Time",
        "preferred_time": "Preferred Time",
        "budget": "Budget",
        "company": "Company",
        "location": "Location",
        "project_description": "Project",
        "main_challenge": "Challenge",
        "business_type": "Business Type",
    }

    lines = [
        f"📱 Phone: {phone}",
        f"🏢 Business: {business_name}",
        "",
        "📋 Lead Details:",
    ]

    for key, value in collected_data.items():
        if key in _INTERNAL_KEYS:
            continue
        label = label_map.get(key, key.replace("_", " ").title())
        lines.append(f"  • {label}: {value}")

    lines.append("")
    lines.append("🤖 Booked via WhatsApp Bot")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def check_slot_availability(
    calendar_id: str,
    google_credentials: dict,
    start_dt: datetime,
    end_dt: datetime,
) -> bool:
    """Returns True if the slot is free, False if already booked."""
    try:
        creds = _get_credentials(google_credentials)
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        body = {
            "timeMin": start_dt.isoformat(),
            "timeMax": end_dt.isoformat(),
            "timeZone": "Asia/Kolkata",
            "items": [{"id": calendar_id}],
        }
        result = service.freebusy().query(body=body).execute()
        busy = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])
        return len(busy) == 0
    except Exception as e:
        logger.error(f"❌ Slot check error: {e}")
        return True  # fail open — assume free


def find_next_available_slot(
    calendar_id: str,
    google_credentials: dict,
    preferred_dt: datetime,
    duration_minutes: int = 30,
    start_hour: int = 9,
    end_hour: int = 18,
    allowed_days: list | None = None,
    max_days: int = 7,
) -> datetime | None:
    """
    Find the next free slot after preferred_dt.
    Checks 30-min increments within working hours for up to max_days.
    Returns the first free datetime or None if none found.
    """
    try:
        if allowed_days is None:
            allowed_days = list(range(7))

        creds = _get_credentials(google_credentials)
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        # Start from the next 30-min boundary after preferred_dt
        current = preferred_dt + timedelta(minutes=30)
        excess = current.minute % 30
        if excess:
            current = current + timedelta(minutes=30 - excess)
        current = current.replace(second=0, microsecond=0)

        end_search = preferred_dt + timedelta(days=max_days)

        # Fetch all busy intervals in range in one API call
        body = {
            "timeMin": current.isoformat(),
            "timeMax": end_search.isoformat(),
            "timeZone": "Asia/Kolkata",
            "items": [{"id": calendar_id}],
        }
        result = service.freebusy().query(body=body).execute()
        busy_slots = result.get("calendars", {}).get(calendar_id, {}).get("busy", [])
        busy_ranges = []
        for slot in busy_slots:
            bs = datetime.fromisoformat(slot["start"].replace("Z", "+00:00")).astimezone(IST)
            be = datetime.fromisoformat(slot["end"].replace("Z", "+00:00")).astimezone(IST)
            busy_ranges.append((bs, be))

        while current < end_search:
            if current.weekday() not in allowed_days:
                current = (current + timedelta(days=1)).replace(
                    hour=start_hour, minute=0, second=0, microsecond=0
                )
                continue
            if current.hour < start_hour:
                current = current.replace(hour=start_hour, minute=0, second=0, microsecond=0)
                continue
            if current.hour >= end_hour:
                current = (current + timedelta(days=1)).replace(
                    hour=start_hour, minute=0, second=0, microsecond=0
                )
                continue

            slot_end = current + timedelta(minutes=duration_minutes)
            is_free = all(
                slot_end <= bs or current >= be
                for bs, be in busy_ranges
            )
            if is_free:
                return current

            current += timedelta(minutes=30)

        return None
    except Exception as e:
        logger.error(f"❌ Find-slot error: {e}")
        return None


def create_calendar_event(
    business_name: str,
    calendar_id: str,
    google_credentials: dict,
    collected_data: dict,
    phone: str,
):
    """
    Create a Google Calendar event from collected lead data.

    Date/time resolution priority:
    1. Parse "date" + "time" fields from collected_data using natural language parser
    2. Fall back to tomorrow 10:00 AM IST if parsing fails
    """
    try:
        creds = _get_credentials(google_credentials)
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        name = collected_data.get("name", phone)
        service_label = (
            collected_data.get("service_type")
            or collected_data.get("reason")
            or "Consultation"
        )

        # ── Parse date ────────────────────────────────────────────────────
        raw_date = (
            collected_data.get("date")
            or collected_data.get("preferred_time")
            or collected_data.get("appointment_date")
        )
        raw_time = (
            collected_data.get("time")
            or collected_data.get("appointment_time")
        )

        date_dt = _parse_date(raw_date)
        time_hm = _parse_time(raw_time)

        if date_dt:
            hour, minute = time_hm if time_hm else (10, 0)
            start_dt = date_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            logger.info(f"📅 Parsed event time: {start_dt} from date='{raw_date}' time='{raw_time}'")
        else:
            # Fallback: tomorrow at 10 AM
            start_dt = (datetime.now(IST) + timedelta(days=1)).replace(
                hour=10, minute=0, second=0, microsecond=0
            )
            logger.warning(
                f"⚠️ Could not parse date '{raw_date}' — defaulting to tomorrow 10 AM"
            )

        end_dt = start_dt + timedelta(minutes=30)

        description = _build_description(phone, business_name, collected_data)

        event_body = {
            "summary": f"📋 {name} — {service_label}",
            "description": description,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 60},   # 1 hr before
                    {"method": "popup", "minutes": 10},   # 10 min before
                ],
            },
        }

        result = service.events().insert(
            calendarId=calendar_id,
            sendUpdates="none",
            body=event_body,
        ).execute()

        link = result.get("htmlLink", "")
        logger.info(f"📅 Event created: {start_dt.strftime('%d %b %Y %I:%M %p')} | {name} | {link}")
        return link

    except Exception as e:
        logger.error(f"❌ Calendar error: {e}")
        return None
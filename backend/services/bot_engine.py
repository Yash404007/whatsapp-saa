"""
Multi-tenant bot engine — Strict 2-phase approach with field validation.
Supports any fields the client configures.
"""

import json
import asyncio
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from models.client import Client
from models.conversation import Conversation, Lead
from services.ai_service import get_ai_reply
from services.email_service import send_confirmation_email
from services.sheets_service import add_lead_to_sheets
from services.calendar_service import create_calendar_event


RESET_WORDS = {"reset", "restart", "start over", "hi", "hello", "hey",
               "start", "new", "hii", "helo", "menu", "home"}

BOOKING_SIGNALS = {
    "book", "schedule", "consultation", "call", "meeting",
    "interested", "proceed", "let's go", "ready", "connect",
    "talk", "discuss", "i want", "i need", "get started",
    "sign up", "begin", "hire", "work with"
}

FIELD_QUESTIONS = {
    "name": "What's your full name?",
    "email": "What's your email address?",
    "phone": "What's your phone number?",
    "budget": "What's your budget range?",
    "timeline": "What's your preferred timeline?",
    "service_type": "What service are you looking for?",
    "company": "What's your company name?",
    "project_description": "Briefly describe your project?",
    "location": "Where are you based?",
    "reason": "What's the reason for your visit?",
    "date": "What's your preferred date?",
    "time": "What time works best?",
    "main_challenge": "What's your biggest business challenge?",
    "preferred_time": "When's a good time for a call?",
    "business_type": "What type of business do you run?",
}

# Fields that need strict validation
STRICT_FIELDS = {"email", "phone", "budget", "name"}

# Fields that accept any answer
LOOSE_FIELDS = {
    "timeline", "service_type", "company", "project_description",
    "location", "reason", "date", "time", "main_challenge",
    "preferred_time", "business_type"
}

MAX_CHAT_TURNS = 4


async def process_message(phone: str, user_text: str, client: Client, db: Session) -> str:
    lower = user_text.lower().strip()

    conversation = db.query(Conversation).filter(
        Conversation.client_id == client.id,
        Conversation.phone == phone,
        Conversation.is_complete == False
    ).first()

    if lower in RESET_WORDS:
        if conversation:
            db.delete(conversation)
            db.commit()
        conversation = None

    if not conversation:
        conversation = Conversation(
            client_id=client.id,
            phone=phone,
            stage="greeting",
            history=[],
            collected={}
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    history = list(conversation.history or [])
    history.append({"role": "user", "parts": [{"text": user_text}]})

    reply = await _handle_stage(conversation, user_text, lower, client, db, phone)

    history.append({"role": "model", "parts": [{"text": reply}]})

    if len(history) > 40:
        history = history[-40:]

    conversation.history = history
    conversation.updated_at = datetime.utcnow()
    db.commit()

    return reply


async def _handle_stage(
    conversation: Conversation,
    user_text: str,
    lower: str,
    client: Client,
    db: Session,
    phone: str = ""
) -> str:

    stage = conversation.stage
    collected = dict(conversation.collected or {})
    fields = list(client.collect_fields or [])
    system_prompt = client.system_prompt or ""
    chat_turns = len([h for h in conversation.history if h.get("role") == "user"])

    logger.info(f"🔍 Stage={stage} | turns={chat_turns} | collected={collected}")

    # ── GREETING ──────────────────────────────────────────────────
    if stage == "greeting":
        conversation.stage = "chatting"
        db.commit()
        return await get_ai_reply(
            [],
            user_text,
            system_prompt,
            client.groq_api_key,
            f"""Send a short powerful welcome. EXACT format:

*Welcome to {client.business_name}!* 🚀
[1 punchy line about impact]

*We help with:*
✅ [4-5 services]

What can we help you with today? 👇

Max 8 lines. Use ✅ for lists. No asterisk bullets."""
        )

    # ── FREE CHATTING ─────────────────────────────────────────────
    if stage == "chatting":
        has_booking_intent = any(w in lower for w in BOOKING_SIGNALS)
        should_push = chat_turns >= MAX_CHAT_TURNS

        logger.info(f"🔍 intent={has_booking_intent} | push={should_push} | turns={chat_turns}")

        if (should_push or has_booking_intent) and fields:
            missing = [f for f in fields if not collected.get(f)]
            if missing:
                conversation.stage = "collecting"
                db.commit()
                first_field = missing[0]
                question = FIELD_QUESTIONS.get(
                    first_field,
                    f"Can you share your {first_field.replace('_', ' ')}?"
                )
                transition = await get_ai_reply(
                    conversation.history[:-1],
                    user_text,
                    system_prompt,
                    client.groq_api_key,
                    "Write ONE warm sentence saying you'd love to connect them with the team. No question. Max 1 line."
                )
                return f"{transition}\n\n*{question}* 😊"

        return await get_ai_reply(
            conversation.history[:-1],
            user_text,
            system_prompt,
            client.groq_api_key,
            """Answer confidently and warmly.
STRICT RULES:
- Max 4 lines
- Use *bold* for key points
- Use ✅ for lists max 3 items
- End with ONE short question
- No payment or bank details ever
- No asterisk bullet points"""
        )

    # ── COLLECTING FIELDS ─────────────────────────────────────────
    if stage == "collecting":
        missing_fields = [f for f in fields if not collected.get(f)]

        if not missing_fields:
            conversation.stage = "confirming"
            db.commit()
            return _build_summary(collected)

        current_field = missing_fields[0]
        answer = user_text.strip()

        # Validate answer
        is_valid = _validate_field(current_field, answer)

        if not is_valid:
            question = FIELD_QUESTIONS.get(
                current_field,
                f"Can you share your {current_field.replace('_', ' ')}?"
            )
            logger.warning(f"⚠️ Invalid answer for {current_field}: {answer}")
            return f"Hmm, that doesn't look right 😊\n\n*{question}*"

        collected[current_field] = answer
        conversation.collected = collected
        db.commit()

        logger.info(f"✅ Saved {current_field} = {answer}")

        still_missing = [f for f in fields if not collected.get(f)]

        if not still_missing:
            conversation.stage = "confirming"
            db.commit()
            return _build_summary(collected)

        next_field = still_missing[0]
        question = FIELD_QUESTIONS.get(
            next_field,
            f"Can you share your {next_field.replace('_', ' ')}?"
        )
        return f"Got it! ✅\n\n*{question}* 😊"

    # ── CONFIRMING ────────────────────────────────────────────────
    if stage == "confirming":
        yes_words = {"yes", "confirm", "ok", "okay", "haan", "ha", "correct",
                     "right", "sure", "proceed", "yess", "yep", "yeah",
                     "perfect", "great", "looks good", "confirmed", "go ahead"}
        no_words = {"no", "nahi", "change", "wrong", "edit", "modify", "update"}

        if any(w in lower for w in yes_words):
            logger.info(f"✅ Confirmed! collected={conversation.collected}")

            lead = Lead(
                client_id=client.id,
                phone=phone,
                data=conversation.collected,
                status="new"
            )
            db.add(lead)
            conversation.is_complete = True
            conversation.stage = "completed"
            db.commit()

            # Send email
            if client.use_email and client.gmail_sender and client.gmail_password:
                email = conversation.collected.get("email")
                if email:
                    asyncio.create_task(
                        asyncio.to_thread(
                            send_confirmation_email,
                            email,
                            client.business_name,
                            client.bot_name,
                            conversation.collected,
                            client.gmail_sender,
                            client.gmail_password,
                        )
                    )
                    logger.info(f"📧 Email task created for {email}")

            # Add to sheets with history
            if client.use_sheets and client.google_credentials and client.sheets_id:
                asyncio.create_task(
                    asyncio.to_thread(
                        add_lead_to_sheets,
                        client.business_name,
                        phone,
                        conversation.collected,
                        client.google_credentials,
                        client.sheets_id,
                        conversation.history,
                    )
                )
                logger.info("📊 Sheets task created")

            # Create calendar event
            if client.use_calendar and client.google_credentials and client.calendar_id:
                asyncio.create_task(
                    asyncio.to_thread(
                        create_calendar_event,
                        client.business_name,
                        client.calendar_id,
                        client.google_credentials,
                        conversation.collected,
                        phone,
                    )
                )
                logger.info("📅 Calendar task created")

            name = conversation.collected.get("name", "there")
            email = conversation.collected.get("email", "")
            return (
                f"*🎉 You're all set, {name}!*\n\n"
                f"Our team at *{client.business_name}* will reach out shortly.\n\n"
                f"{'📧 Confirmation sent to ' + email + chr(10) if email else ''}"
                f"📞 Urgent? Call {client.contact_phone or 'us'}\n\n"
                f"_Thank you for choosing {client.business_name}. "
                f"Looking forward to growing your business!_ 🚀"
            )

        if any(w in lower for w in no_words):
            conversation.stage = "collecting"
            conversation.collected = {}
            db.commit()
            if fields:
                first_field = fields[0]
                question = FIELD_QUESTIONS.get(
                    first_field,
                    f"Can you share your {first_field.replace('_', ' ')}?"
                )
                return f"No problem! Let's start fresh.\n\n*{question}* 😊"
            return "No problem! How can we help? 😊"

        return "Please reply *YES* to confirm ✅ or *NO* to make changes 😊"

    # ── COMPLETED ─────────────────────────────────────────────────
    if stage == "completed":
        return await get_ai_reply(
            conversation.history[:-1],
            user_text,
            system_prompt,
            client.groq_api_key,
            f"""User already booked. Answer helpfully.
Do NOT restart conversation.
Do NOT ask for details again.
For urgent: {client.contact_phone}
Max 3 lines."""
        )

    # Fallback
    conversation.stage = "greeting"
    db.commit()
    return f"*Welcome to {client.business_name}!* 👋\n\nI'm {client.bot_name}. How can I help? 😊"


def _build_summary(collected: dict) -> str:
    """Build clean hardcoded summary."""
    lines = []
    for key, value in collected.items():
        label = key.replace("_", " ").title()
        lines.append(f"*{label}:* {value}")
    summary = "\n".join(lines)
    return (
        f"*📋 Almost done! Here's your summary:*\n\n"
        f"{summary}\n\n"
        f"─────────────────\n"
        f"Reply *YES* to confirm ✅\n"
        f"Reply *NO* to make changes"
    )


def _validate_field(field: str, value: str) -> bool:
    """
    Flexible validation:
    - Strict fields: email, phone, budget, name
    - All other fields: accept any reasonable answer
    """
    if not value or len(value.strip()) < 1:
        return False

    value_lower = value.lower().strip()

    # ── EMAIL ──────────────────────────────────────────────────
    if field == "email":
        return "@" in value and "." in value.split("@")[-1]

    # ── PHONE ──────────────────────────────────────────────────
    if field == "phone":
        digits = "".join(filter(str.isdigit, value))
        return len(digits) >= 7

    # ── BUDGET ─────────────────────────────────────────────────
    if field == "budget":
        has_number = any(c.isdigit() for c in value)
        has_currency = any(w in value_lower for w in [
            "k", "l", "lakh", "lac", "thousand", "usd", "inr",
            "₹", "$", "cr", "crore", "million", "free", "discuss",
            "negotiable", "flexible"
        ])
        return has_number or has_currency

    # ── NAME ───────────────────────────────────────────────────
    if field == "name":
        # Reject obvious non-names
        non_name_phrases = [
            "discuss", "meeting", "call", "schedule", "book",
            "yes", "no", "ok", "okay", "sure", "website", "service",
            "help", "need", "want", "hi", "hello", "hey", "let's",
            "lets", "can we", "i want", "i need", "what", "how",
            "when", "where", "why", "which"
        ]
        # Name should not be a single common word that is not a name
        if value_lower in non_name_phrases:
            return False
        # Name should be at least 2 chars and contain letters
        has_letters = any(c.isalpha() for c in value)
        return has_letters and len(value.strip()) >= 2

    # ── ALL OTHER FIELDS — Accept any reasonable answer ─────────
    # Just reject empty or very short single-character answers
    has_content = len(value.strip()) >= 2
    return has_content
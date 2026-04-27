"""
Multi-tenant bot engine.
Handles conversations for any client based on their config.
"""

import json
import asyncio
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from models.client import Client
from models.conversation import Conversation, Lead
from services.ai_service import get_ai_reply, extract_fields
from services.email_service import send_confirmation_email
from services.sheets_service import add_lead_to_sheets


RESET_WORDS = {"reset", "restart", "start over", "hi", "hello", "hey",
               "start", "new", "hii", "helo"}


async def process_message(phone: str, user_text: str, client: Client, db: Session) -> str:
    """Main entry point — process incoming message for a specific client."""

    lower = user_text.lower().strip()

    # Get or create conversation
    conversation = db.query(Conversation).filter(
        Conversation.client_id == client.id,
        Conversation.phone == phone,
        Conversation.is_complete == False
    ).first()

    # Reset if greeting word
    if lower in RESET_WORDS:
        if conversation:
            db.delete(conversation)
            db.commit()
        conversation = None

    # Create new conversation if needed
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

    # Add user message to history
    history = conversation.history or []
    history.append({"role": "user", "parts": [{"text": user_text}]})

    # Get reply
    reply = await _handle_stage(conversation, user_text, lower, client, db)

    # Add reply to history
    history.append({"role": "model", "parts": [{"text": reply}]})

    # Keep last 40 messages
    if len(history) > 40:
        history = history[-40:]

    # Update conversation
    conversation.history = history
    conversation.updated_at = datetime.utcnow()
    db.commit()

    return reply


async def _handle_stage(
    conversation: Conversation,
    user_text: str,
    lower: str,
    client: Client,
    db: Session
) -> str:

    stage = conversation.stage
    collected = conversation.collected or {}
    fields = client.collect_fields or []
    system_prompt = client.system_prompt or ""

    # ── GREETING ──────────────────────────────────────────────────
    if stage == "greeting":
        conversation.stage = "collecting"
        db.commit()
        return await get_ai_reply(
            conversation.history[:-1],
            user_text,
            system_prompt,
            client.groq_api_key,
            f"User just started. Greet them warmly as {client.bot_name} from {client.business_name}. Ask for their {fields[0] if fields else 'name'} only."
        )

    # ── COLLECTING FIELDS ─────────────────────────────────────────
    if stage == "collecting":
        missing_fields = [f for f in fields if not collected.get(f)]

        if missing_fields:
            extracted = await extract_fields(user_text, missing_fields, client.groq_api_key)

            for field, value in extracted.items():
                if value:
                    collected[field] = value

            conversation.collected = collected
            db.commit()

            still_missing = [f for f in fields if not collected.get(f)]

            if still_missing:
                return await get_ai_reply(
                    conversation.history[:-1],
                    user_text,
                    system_prompt,
                    client.groq_api_key,
                    f"Collected so far: {json.dumps(collected)}. Still need: {', '.join(still_missing)}. Ask for ONLY the next missing field: {still_missing[0]}. One question only."
                )
            else:
                conversation.stage = "confirming"
                db.commit()
                return await get_ai_reply(
                    conversation.history[:-1],
                    user_text,
                    system_prompt,
                    client.groq_api_key,
                    f"All details collected: {json.dumps(collected)}. Show a SHORT summary and ask user to reply YES to confirm or NO to change. Keep it brief."
                )

    # ── CONFIRMING ────────────────────────────────────────────────
    if stage == "confirming":
        yes_words = {"yes", "confirm", "ok", "okay", "haan", "ha", "correct", "right", "sure", "proceed"}
        no_words  = {"no", "nahi", "change", "wrong", "edit", "modify"}

        if any(w in lower for w in yes_words):
            # Save as lead
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

            # Debug log
            logger.info(f"📧 Checking email | use_email={client.use_email} | gmail={client.gmail_sender} | collected={conversation.collected}")

            # Send email if enabled
            if client.use_email and client.gmail_sender and client.gmail_password:
                email = conversation.collected.get("email")
                logger.info(f"📧 Email field found = {email}")
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
                else:
                    logger.warning("📧 No email field in collected data — skipping email")
            else:
                logger.warning(f"📧 Email not triggered — use_email={client.use_email} gmail={client.gmail_sender}")

            # Add to sheets if enabled
            if client.use_sheets and client.google_credentials:
                asyncio.create_task(
                    asyncio.to_thread(
                        add_lead_to_sheets,
                        client.business_name,
                        phone,
                        conversation.collected,
                        client.google_credentials,
                    )
                )
                logger.info("📊 Sheets task created")

            return await get_ai_reply(
                conversation.history[:-1],
                user_text,
                system_prompt,
                client.groq_api_key,
                f"User confirmed! Details saved: {json.dumps(conversation.collected)}. Thank them warmly in 1-2 sentences and tell them what happens next. Mention they can call {client.contact_phone} for any changes."
            )

        if any(w in lower for w in no_words):
            conversation.stage = "collecting"
            conversation.collected = {}
            db.commit()
            return f"No problem! Let's start over. What's your {fields[0] if fields else 'name'}? 😊"

        return "Please reply *YES* to confirm or *NO* to change details. 😊"

    # ── COMPLETED ─────────────────────────────────────────────────
    if stage == "completed":
        return await get_ai_reply(
            conversation.history[:-1],
            user_text,
            system_prompt,
            client.groq_api_key,
            f"User already submitted their details. Answer any questions about {client.business_name} briefly. For changes tell them to call {client.contact_phone}."
        )

    # Fallback
    conversation.stage = "greeting"
    db.commit()
    return f"Welcome to {client.business_name}! I'm {client.bot_name}. How can I help you today? 😊"
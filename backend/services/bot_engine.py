"""
Multi-tenant bot engine — Premium AI-first conversational approach.
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
from services.calendar_service import create_calendar_event


RESET_WORDS = {"reset", "restart", "start over", "hi", "hello", "hey",
               "start", "new", "hii", "helo", "menu", "home"}

# When user shows buying intent
BOOKING_SIGNALS = {
    "book", "schedule", "consultation", "call", "meeting", "appointment",
    "interested", "proceed", "let's go", "ready", "connect", "yes",
    "talk", "discuss", "help me", "i want", "i need", "get started",
    "sign up", "onboard", "start", "begin", "hire", "work with"
}


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

    logger.info(f"🔍 Stage={stage} | collected={collected} | fields={fields}")

    # ── GREETING ──────────────────────────────────────────────────
    if stage == "greeting":
        conversation.stage = "chatting"
        db.commit()
        return await get_ai_reply(
            [],
            user_text,
            system_prompt,
            client.groq_api_key,
            """Give a POWERFUL welcome message. Use this EXACT WhatsApp format:

*Welcome to [Business Name]* 🚀

[1 line about what you do and your impact]

*We Help Businesses With:*
✅ [Service 1]
✅ [Service 2]  
✅ [Service 3]
✅ [Service 4]
✅ [Service 5]

[1 motivational line about results]

*How can we help YOU grow today?* 👇

Make it feel premium, exciting and trustworthy. Use their actual services."""
        )

    # ── FREE CHATTING ─────────────────────────────────────────────
    if stage == "chatting":
        # Try to extract fields naturally from conversation
        if fields:
            missing = [f for f in fields if not collected.get(f)]
            if missing:
                extracted = await extract_fields(user_text, missing, client.groq_api_key)
                for field, value in extracted.items():
                    if value:
                        collected[field] = value
                conversation.collected = collected
                db.commit()

        all_collected = all(collected.get(f) for f in fields)
        has_booking_intent = any(w in lower for w in BOOKING_SIGNALS)

        logger.info(f"🔍 booking_intent={has_booking_intent} | all_collected={all_collected} | collected={collected}")

        # All fields collected naturally
        if all_collected and fields:
            conversation.stage = "confirming"
            db.commit()
            return await _show_summary(collected, client, conversation.history[:-1], user_text, system_prompt)

        # User shows booking intent — start collecting remaining fields
        if has_booking_intent and fields:
            missing = [f for f in fields if not collected.get(f)]
            if missing:
                conversation.stage = "collecting"
                db.commit()
                return await get_ai_reply(
                    conversation.history[:-1],
                    user_text,
                    system_prompt,
                    client.groq_api_key,
                    f"""User wants to proceed. Transition smoothly to collecting their details.
Already collected: {json.dumps(collected)}
Next field needed: {missing[0]}

Say something like "Awesome! Let's get you started 🎯" then ask ONLY for their {missing[0]} in a warm engaging way. Make it feel natural not like a form."""
                )

        # Keep the conversation going with AI
        return await get_ai_reply(
            conversation.history[:-1],
            user_text,
            system_prompt,
            client.groq_api_key,
            f"""Continue the sales conversation naturally.
Already collected: {json.dumps(collected)}

Guidelines:
- Answer their question with expertise and confidence
- If they mention a problem, show empathy then present the solution
- Use WhatsApp formatting: *bold* for emphasis, emojis for engagement
- Share a relevant result or case study if possible
- Naturally guide toward booking a free consultation
- If they ask about pricing, give a range and explain value
- Keep replies focused and max 5-6 lines
- End with an engaging question to keep conversation going"""
        )

    # ── COLLECTING FIELDS ─────────────────────────────────────────
    if stage == "collecting":
        missing_fields = [f for f in fields if not collected.get(f)]
        logger.info(f"🔍 missing_fields={missing_fields}")

        if not missing_fields:
            conversation.stage = "confirming"
            db.commit()
            return await _show_summary(collected, client, conversation.history[:-1], user_text, system_prompt)

        # Save current input to next missing field
        current_field = missing_fields[0]
        collected[current_field] = user_text.strip()
        conversation.collected = collected
        db.commit()

        logger.info(f"✅ Saved {current_field} = {user_text.strip()}")

        still_missing = [f for f in fields if not collected.get(f)]

        if not still_missing:
            conversation.stage = "confirming"
            db.commit()
            return await _show_summary(collected, client, conversation.history[:-1], user_text, system_prompt)

        # Ask for next field naturally using AI
        next_field = still_missing[0]
        return await get_ai_reply(
            conversation.history[:-1],
            user_text,
            system_prompt,
            client.groq_api_key,
            f"""Acknowledge what they just said warmly, then ask ONLY for their *{next_field}*.
Already collected: {json.dumps(collected)}
Be natural, warm and brief. One question only. Use an emoji. Max 2 lines."""
        )

    # ── CONFIRMING ────────────────────────────────────────────────
    if stage == "confirming":
        yes_words = {"yes", "confirm", "ok", "okay", "haan", "ha", "correct",
                     "right", "sure", "proceed", "yess", "yep", "yeah", "perfect",
                     "great", "looks good", "confirmed", "go ahead"}
        no_words  = {"no", "nahi", "change", "wrong", "edit", "modify", "update"}

        logger.info(f"🔍 Confirming | lower={lower}")

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

            # Add to sheets
            if client.use_sheets and client.google_credentials and client.sheets_id:
                asyncio.create_task(
                    asyncio.to_thread(
                        add_lead_to_sheets,
                        client.business_name,
                        phone,
                        conversation.collected,
                        client.google_credentials,
                        client.sheets_id,
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

            # Beautiful confirmation message
            return await get_ai_reply(
                conversation.history[:-1],
                user_text,
                system_prompt,
                client.groq_api_key,
                f"""User confirmed! Details saved: {json.dumps(conversation.collected)}

Send a POWERFUL confirmation message in this format:

*🎉 You're All Set!*

[Warm congratulations line]

*What Happens Next:*
📞 Our team will contact you within [timeframe]
📧 Check your email for confirmation
🚀 [What they can expect]

*Your Details:*
[Show key details cleanly]

[Motivational closing line about their business growth]

📞 Urgent? Call: {client.contact_phone}

Make it exciting and make them feel they made the right decision!"""
            )

        if any(w in lower for w in no_words):
            conversation.stage = "chatting"
            conversation.collected = {}
            db.commit()
            return await get_ai_reply(
                conversation.history[:-1],
                user_text,
                system_prompt,
                client.groq_api_key,
                "User wants to change details. Acknowledge warmly and ask what they'd like to update. Be friendly."
            )

        return (
            "Please reply *YES* to confirm or *NO* to make changes 😊\n\n"
            "We're excited to work with you! 🚀"
        )

    # ── COMPLETED ─────────────────────────────────────────────────
    if stage == "completed":
        return await get_ai_reply(
            conversation.history[:-1],
            user_text,
            system_prompt,
            client.groq_api_key,
            f"""User already booked. Answer their questions about {client.business_name} as a trusted advisor.
Be helpful, warm and professional.
For urgent matters tell them to call {client.contact_phone}.
Use WhatsApp formatting for readability."""
        )

    # Fallback
    conversation.stage = "greeting"
    db.commit()
    return f"*Welcome to {client.business_name}!* 👋\n\nI'm {client.bot_name}. How can I help you today? 😊"


async def _show_summary(collected: dict, client: Client, history: list, user_text: str, system_prompt: str) -> str:
    """Show a beautiful summary before confirmation."""
    return await get_ai_reply(
        history,
        user_text,
        system_prompt,
        client.groq_api_key,
        f"""Show a beautiful confirmation summary in WhatsApp format:

*📋 Here's Your Summary*

[For each field show as:]
*Field Name:* Value

[Then add:]

✅ Everything look good?

Reply *YES* to confirm your booking
Reply *NO* to make any changes

[Add 1 exciting line about what they're about to achieve]

Details to show: {json.dumps(collected)}"""
    )
"""
Multi-tenant bot engine — Service-first lead qualification flow.

FLOW:
  greeting → service_selection → service_qualification → chatting → collecting → confirming → completed

FIXES FROM ORIGINAL:
1. Stage machine was inconsistent — "greeting" immediately set to "chatting" before returning,
   so the next message entered chatting with stale turn count.
2. chat_turns counted from full history AFTER appending user message, causing off-by-one.
3. Off-topic detection in collecting was over-eager — flagged loose-field answers like
   "when is next week good?" as off-topic even though they're valid answers.
4. _is_off_topic for loose fields only flagged >3-word question starters but the check
   `len(v.split()) > 3` used total words, not question-starter words — fixed to check
   the whole phrase properly.
5. Confirming stage "no" branch reset collected={} but didn't handle the case where
   fields list is empty — now falls back gracefully.
6. process_message appended user message to history BEFORE _handle_stage, so history
   passed into AI helpers always included the current user turn twice (once pre-pended,
   once via conversation.history). Fixed: history append happens after stage handling.
7. Budget validation rejected answers like "let's discuss" — "discuss" is now valid.
8. Name validation: single short words like "Ali" or "Jo" were fine, but the check
   `word[0].islower()` failed for ALL-CAPS input like "RAHUL" — fixed.
9. Greeting reply was generated via AI but stage was already set to "chatting" before
   the reply was sent, meaning if AI call failed mid-way the stage was already corrupted.
   Now stage transitions happen AFTER successful reply generation where possible.
10. MAX_CHAT_TURNS push logic: should_push fired even when user was already in collecting.
    Now only applies in the "chatting" stage.

NEW FLOW:
- greeting        → Welcome message + service menu
- service_selection → User picks a service; bot asks service-specific qualifying question
- service_qualification → User answers qualifier; bot may answer follow-up questions
                           but steers back to lead capture after MAX_QUALIFY_TURNS
- collecting      → Name → Email → Date (configurable via client.collect_fields)
- confirming      → Summary → YES / NO
- completed       → Post-booking help
"""

import re
import asyncio
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from models.client import Client
from models.conversation import Conversation, Lead
from services.ai_service import get_ai_reply
from services.email_service import send_confirmation_email
from services.sheets_service import add_lead_to_sheets
from services.calendar_service import (
    create_calendar_event,
    check_slot_availability,
    find_next_available_slot,
)
from services.calendar_service import _parse_date as _cal_parse_date, _parse_time as _cal_parse_time


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

RESET_WORDS = {
    "reset", "restart", "start over", "start", "new", "menu", "home",
    "hi", "hii", "hiii", "hiiii", "hiiiii",
    "hello", "helo", "helloo",
    "hey", "heyy", "heyyy",
}

SERVICES = {
    "1": "Website",
    "2": "Branding",
    "3": "AI Integration",
    "4": "Social Media",
    "website": "Website",
    "branding": "Branding",
    "ai": "AI Integration",
    "ai integration": "AI Integration",
    "social": "Social Media",
    "social media": "Social Media",
}

# Service-specific qualifying questions (multi-step for AI Integration)
SERVICE_QUESTIONS = {
    "Website": [
        "What type of website are you looking for? _(e.g. portfolio, e-commerce, landing page, SaaS)_"
    ],
    "Branding": [
        "What type of brand are you building? _(e.g. personal brand, startup, product, agency)_"
    ],
    "AI Integration": [
        "Where do you want to integrate AI? _(e.g. chatbot, automation, analytics, customer support)_",
        "What result are you looking for from AI integration? _(e.g. save time, reduce costs, improve UX)_",
    ],
    "Social Media": [
        "What type of brand are you promoting on social media? _(e.g. personal brand, e-commerce, local business)_"
    ],
}

# Scope keywords per service — answers outside these get steered to meeting
SERVICE_SCOPE = {
    "Website": [
        "website", "web", "page", "landing", "ecommerce", "e-commerce", "portfolio",
        "saas", "blog", "shop", "store", "cms", "wordpress", "design", "development",
        "responsive", "mobile", "seo", "hosting", "domain",
    ],
    "Branding": [
        "brand", "logo", "identity", "color", "typography", "style", "guide", "visual",
        "palette", "name", "tagline", "positioning", "persona", "startup", "product",
        "agency", "personal",
    ],
    "AI Integration": [
        "ai", "chatbot", "bot", "automation", "gpt", "openai", "anthropic", "claude",
        "machine learning", "ml", "nlp", "analytics", "data", "workflow", "crm",
        "integration", "api", "automate", "support", "customer",
    ],
    "Social Media": [
        "social", "instagram", "facebook", "twitter", "x", "linkedin", "tiktok",
        "content", "post", "reel", "story", "caption", "strategy", "growth",
        "followers", "engagement", "ads", "campaign", "brand", "promote",
    ],
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
    "date": "What's your preferred date for a call? _(e.g. Monday afternoon, 15th Jan)_",
    "time": "What time works best?",
    "main_challenge": "What's your biggest business challenge?",
    "preferred_time": "When's a good time for a call?",
    "business_type": "What type of business do you run?",
}

FIELD_LABELS = {
    "name": "Name",
    "email": "Email",
    "phone": "Phone",
    "budget": "Budget",
    "timeline": "Timeline",
    "service_type": "Service Type",
    "company": "Company",
    "project_description": "Project Description",
    "location": "Location",
    "reason": "Reason",
    "date": "Preferred Date",
    "time": "Preferred Time",
    "main_challenge": "Main Challenge",
    "preferred_time": "Preferred Time for Call",
    "business_type": "Business Type",
}

STRICT_FIELDS = {"email", "phone", "budget", "name"}
LOOSE_FIELDS = {
    "timeline", "service_type", "company", "project_description",
    "location", "reason", "date", "time", "main_challenge",
    "preferred_time", "business_type",
}

# Default fields to collect if client doesn't specify
DEFAULT_COLLECT_FIELDS = ["name", "email", "date"]

# Max turns in service_qualification before pushing to collecting
MAX_QUALIFY_TURNS = 3


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

async def process_message(phone: str, user_text: str, client: Client, db: Session) -> str:
    lower = user_text.lower().strip()

    conversation = db.query(Conversation).filter(
        Conversation.client_id == client.id,
        Conversation.phone == phone,
        Conversation.is_complete == False,
    ).first()

    # Reset conversation on trigger words
    if lower in RESET_WORDS:
        if conversation:
            db.delete(conversation)
            db.commit()
        conversation = None

    # Create fresh conversation if needed
    if not conversation:
        conversation = Conversation(
            client_id=client.id,
            phone=phone,
            stage="greeting",
            history=[],
            collected={},
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # FIX: Append user message to history AFTER handling, not before.
    # This prevents the current user turn from appearing in the AI context twice.
    reply = await _handle_stage(conversation, user_text, lower, client, db, phone)

    history = list(conversation.history or [])
    history.append({"role": "user", "parts": [{"text": user_text}]})
    history.append({"role": "model", "parts": [{"text": reply}]})

    # Keep history bounded
    if len(history) > 40:
        history = history[-40:]

    conversation.history = history
    conversation.updated_at = datetime.utcnow()
    db.commit()

    return reply


# ─────────────────────────────────────────────────────────────────────────────
# STAGE HANDLER
# ─────────────────────────────────────────────────────────────────────────────

async def _handle_stage(
    conversation: Conversation,
    user_text: str,
    lower: str,
    client: Client,
    db: Session,
    phone: str = "",
) -> str:

    stage = conversation.stage
    collected = dict(conversation.collected or {})
    fields = list(client.collect_fields or DEFAULT_COLLECT_FIELDS)
    system_prompt = client.system_prompt or ""

    # Count user turns from history (history does NOT yet include current message)
    history = list(conversation.history or [])
    chat_turns = len([h for h in history if h.get("role") == "user"])

    logger.info(f"🔍 Stage={stage} | turns={chat_turns} | collected={list(collected.keys())}")

    # ── GREETING ──────────────────────────────────────────────────────────────
    if stage == "greeting":
        reply = _build_welcome(client)
        # Skip service selection if no services are configured for this client
        if client.services:
            conversation.stage = "service_selection"
        else:
            conversation.stage = "collecting"
        db.commit()
        return reply

    # ── SERVICE SELECTION ─────────────────────────────────────────────────────
    if stage == "service_selection":
        services = _detect_services(lower, list(client.services or []))

        if not services:
            menu = _build_service_menu(client)
            if _is_question(lower):
                ai_answer = await get_ai_reply(
                    history, user_text, system_prompt, client.groq_api_key,
                    "Answer this question briefly in max 3 lines using ONLY information from your "
                    "business description. Do NOT invent any facts or details. Do NOT end with a question.",
                )
                return f"{ai_answer}\n\n───────────────────\n{menu}\n\n_Reply with a number_ 👆"
            return (
                f"Please pick a service:\n\n"
                f"{menu}\n\n"
                "_Reply with a number_ 👆"
            )

        collected["_qualify_step"] = 0

        if len(services) > 1:
            # Multiple services — store joined, skip qualification, go straight to collecting
            collected["service_type"] = ", ".join(services)
            conversation.collected = collected
            db.commit()
            names = " & ".join(f"*{s}*" for s in services)
            intro = f"Great choices! 🚀 {names} — we can definitely help with all of that.\n\n"
            transition = _transition_to_collecting(conversation, fields, collected, db)
            return intro + transition

        # Single service — proceed with qualification
        service = services[0]
        collected["service_type"] = service
        conversation.collected = collected
        conversation.stage = "service_qualification"
        db.commit()

        questions = SERVICE_QUESTIONS.get(service, [])
        if not questions:
            return _transition_to_collecting(conversation, fields, collected, db)

        first_q = questions[0]
        return (
            f"Great choice! 🚀 *{service}* is one of our strongest areas.\n\n"
            f"*{first_q}*"
        )

    # ── SERVICE QUALIFICATION ─────────────────────────────────────────────────
    if stage == "service_qualification":
        service = collected.get("service_type", "")
        qualify_step = int(collected.get("_qualify_step", 0))
        qualify_turns = int(collected.get("_qualify_turns", 0))
        questions = SERVICE_QUESTIONS.get(service, [])

        # Check if the message is off-topic / a follow-up question
        if _is_question(lower):
            # Is it in scope for their chosen service?
            in_scope = _is_in_scope(lower, service)

            if in_scope:
                # Answer the question, then re-ask the current qualifying question
                current_q = questions[qualify_step] if qualify_step < len(questions) else None
                ai_answer = await get_ai_reply(
                    history,
                    user_text,
                    system_prompt,
                    client.groq_api_key,
                    f"""Answer this {service}-related question briefly using ONLY information from your business description.
RULES:
- Max 4 lines
- Use *bold* for key points
- Use ✅ for lists, max 3 items
- Do NOT invent project names, client references, or details not in your description
- Do NOT end with a question""",
                )
                suffix = f"\n\n───────────────────\n*{current_q}* 😊" if current_q else ""
                collected["_qualify_turns"] = qualify_turns + 1
                conversation.collected = collected
                db.commit()
                return f"{ai_answer}{suffix}"
            else:
                # Out of scope — steer to booking
                collected["_qualify_turns"] = qualify_turns + 1
                conversation.collected = collected
                db.commit()
                current_q = questions[qualify_step] if qualify_step < len(questions) else None
                out_of_scope_msg = (
                    "That's a bit outside our current scope, but our team would love to "
                    "discuss it with you in detail! 🙌\n\n"
                    "Let me connect you with the right person.\n\n"
                )
                if current_q:
                    out_of_scope_msg += f"First — *{current_q}* 😊"
                else:
                    # Skip straight to collecting
                    return _transition_to_collecting(conversation, fields, collected, db)
                return out_of_scope_msg

        # Save the qualifying answer
        answer_key = f"_qa_{qualify_step}"
        collected[answer_key] = user_text.strip()
        qualify_step += 1
        qualify_turns += 1
        collected["_qualify_step"] = qualify_step
        collected["_qualify_turns"] = qualify_turns
        conversation.collected = collected
        db.commit()

        # Move to next qualifying question if available
        if qualify_step < len(questions):
            next_q = questions[qualify_step]
            ack = _get_ack()
            return f"{ack}\n\n*{next_q}* 😊"

        # All qualifying questions answered — transition to collecting
        return _transition_to_collecting(conversation, fields, collected, db)

    # ── COLLECTING FIELDS ─────────────────────────────────────────────────────
    if stage == "collecting":
        missing_fields = [f for f in fields if not collected.get(f)]

        if not missing_fields:
            conversation.stage = "confirming"
            db.commit()
            return _build_summary(collected, fields)

        current_field = missing_fields[0]
        answer = user_text.strip()

        # ── Change / correction intent ────────────────────────────────────
        change = _parse_change_intent(lower, answer, collected, fields)
        if change:
            field_to_change, inline_value = change
            if inline_value and _validate_field(field_to_change, inline_value):
                collected[field_to_change] = inline_value
                conversation.collected = collected
                db.commit()
                label = FIELD_LABELS.get(field_to_change, field_to_change.replace("_", " ").title())
                logger.info(f"✏️ Updated {field_to_change} = {inline_value}")
                still_missing = [f for f in fields if not collected.get(f)]
                if not still_missing:
                    conversation.stage = "confirming"
                    db.commit()
                    return f"Updated! ✅\n\n{_build_summary(collected, fields)}"
                return f"Updated *{label}* ✅\n\n{_build_progress(collected, fields)}\n\n─────────────────────────\n*{FIELD_QUESTIONS.get(still_missing[0], 'What is your ' + still_missing[0].replace('_', ' ') + '?')}* 😊"
            else:
                # Ask for the new value
                label = FIELD_LABELS.get(field_to_change, field_to_change.replace("_", " ").title())
                collected.pop(field_to_change, None)
                conversation.collected = collected
                db.commit()
                q = FIELD_QUESTIONS.get(field_to_change, f"What's your {field_to_change.replace('_', ' ')}?")
                return f"Sure, let's update your *{label}*.\n\n*{q}* 😊"

        # ── Auto-detect field from value (email / phone / name mismatch) ──
        detected = _detect_field_from_value(answer, fields)
        if detected and detected != current_field:
            # Validate for the detected field
            if _validate_field(detected, answer):
                collected[detected] = answer
                conversation.collected = collected
                db.commit()
                label = FIELD_LABELS.get(detected, detected.replace("_", " ").title())
                cur_label = FIELD_LABELS.get(current_field, current_field.replace("_", " ").title())
                logger.info(f"🔀 Auto-saved {detected} = {answer}")
                still_missing = [f for f in fields if not collected.get(f)]
                if not still_missing:
                    conversation.stage = "confirming"
                    db.commit()
                    return f"Got your *{label}*! ✅\n\n{_build_summary(collected, fields)}"
                q = FIELD_QUESTIONS.get(still_missing[0], f"What's your {still_missing[0].replace('_', ' ')}?")
                return (
                    f"Got your *{label}*! ✅ Still need your *{cur_label}*.\n\n"
                    f"{_build_progress(collected, fields)}\n\n─────────────────────────\n*{q}* 😊"
                )

        # ── Date field answered with a pure time ("11 am" when asked for date) ──
        _date_fields = {"date", "appointment_date"}
        _time_fields = {"time", "appointment_time", "preferred_time"}
        if current_field in _date_fields and _PURE_TIME_RE.match(answer.lower().strip()):
            # Find the first uncollected time-like field
            time_companion = next((f for f in fields if f in _time_fields and not collected.get(f)), None)
            if time_companion:
                collected[time_companion] = answer
                conversation.collected = collected
                db.commit()
                q_date = FIELD_QUESTIONS.get(current_field, "What date works for you?")
                logger.info(f"🔀 Saved pure-time '{answer}' → {time_companion}, re-asking for date")
                return f"Got your time ✅ What *date* works for you?\n\n*{q_date}* 😊"

        # ── Off-topic / question ──────────────────────────────────────────
        if _is_off_topic_for_field(answer, current_field):
            logger.info(f"🔀 Off-topic for '{current_field}': {answer}")
            q = FIELD_QUESTIONS.get(current_field, f"Can you share your {current_field.replace('_', ' ')}?")
            ai_answer = await get_ai_reply(
                history, answer, system_prompt, client.groq_api_key,
                "Answer the user's question briefly (max 3 lines) using ONLY information "
                "from your business description. Do NOT invent facts, project names, "
                "client references, or any detail not explicitly mentioned. "
                "Do NOT end with a question.",
            )
            return f"{ai_answer}\n\n───────────────────\n*{q}* 😊"

        # ── Format validation ─────────────────────────────────────────────
        if not _validate_field(current_field, answer):
            q = FIELD_QUESTIONS.get(current_field, f"Can you share your {current_field.replace('_', ' ')}?")
            hint = _get_field_hint(current_field)
            logger.warning(f"⚠️ Invalid '{current_field}': {answer}")
            return f"Hmm, that doesn't look right 😊\n\n{hint}*{q}*"

        # ── Working hours check ───────────────────────────────────────────
        if current_field in {"time", "date", "preferred_time"} and client.working_hours:
            if not _is_within_working_hours(answer, client.working_hours):
                q = FIELD_QUESTIONS.get(current_field, f"Can you share your {current_field.replace('_', ' ')}?")
                logger.info(f"⏰ Outside working hours: '{answer}' vs '{client.working_hours}'")
                return (
                    f"⏰ That's outside our working hours.\n\n"
                    f"We're available: *{client.working_hours}*\n\n"
                    f"*{q}* 😊"
                )

        # ── Save ──────────────────────────────────────────────────────────
        collected[current_field] = answer
        conversation.collected = collected
        logger.info(f"✅ Saved {current_field} = {answer}")

        # If user gave date+time together, auto-fill the companion time field
        if current_field in _date_fields:
            time_companion = next(
                (f for f in fields if f in _time_fields and not collected.get(f)), None
            )
            if time_companion:
                extracted_t = _extract_time_str(answer)
                if extracted_t:
                    collected[time_companion] = extracted_t
                    logger.info(f"✅ Auto-extracted {time_companion} = {extracted_t} from date answer")

        db.commit()

        still_missing = [f for f in fields if not collected.get(f)]
        if not still_missing:
            conversation.stage = "confirming"
            db.commit()
            return _build_summary(collected, fields)

        next_field = still_missing[0]
        q = FIELD_QUESTIONS.get(next_field, f"Can you share your {next_field.replace('_', ' ')}?")
        return f"{_build_progress(collected, fields)}\n\n─────────────────────────\n*{q}* 😊"

    # ── CONFIRMING ────────────────────────────────────────────────────────────
    if stage == "confirming":
        # Use word-boundary check to avoid substring false-positives like
        # "ha" matching "change", or "right" matching "alright".
        _lower_words = set(re.findall(r"\b\w+\b", lower))
        yes_single = {
            "yes", "confirm", "ok", "okay", "haan", "ha", "correct",
            "right", "sure", "proceed", "yess", "yep", "yeah",
            "perfect", "great", "confirmed",
        }
        yes_phrases = {"looks good", "go ahead"}
        no_words = {"no", "nahi", "change", "wrong", "edit", "modify", "update"}

        is_yes = bool(_lower_words & yes_single) or any(p in lower for p in yes_phrases)
        is_no  = bool(_lower_words & no_words)

        if is_yes and not is_no:
            logger.info(f"✅ Confirmed! collected={conversation.collected}")

            # ── Calendar slot conflict check ───────────────────────────────
            if client.use_calendar and client.google_credentials and client.calendar_id:
                pending_iso = collected.get("_pending_slot")

                if pending_iso:
                    # User accepted the suggested alt slot — apply it to date/time fields
                    try:
                        from datetime import datetime as _dt
                        from zoneinfo import ZoneInfo as _ZI
                        _IST = _ZI("Asia/Kolkata")
                        alt_start = _dt.fromisoformat(pending_iso)
                        time_str = alt_start.strftime("%I:%M %p").lstrip("0")
                        collected["date"] = f"{alt_start.day} {alt_start.strftime('%B %Y')}"
                        for tf in ("time", "appointment_time", "preferred_time"):
                            if tf in fields:
                                collected[tf] = time_str
                                break
                        collected.pop("_pending_slot", None)
                        conversation.collected = collected
                        logger.info(f"📅 Alt slot applied: {alt_start}")
                    except Exception as _e:
                        logger.warning(f"⚠️ Could not apply pending slot: {_e}")
                        collected.pop("_pending_slot", None)
                        conversation.collected = collected
                else:
                    # Check if the requested slot is already booked
                    start_dt, end_dt = _resolve_slot_dt(collected)
                    if start_dt and end_dt:
                        is_free = check_slot_availability(
                            client.calendar_id, client.google_credentials, start_dt, end_dt
                        )
                        if not is_free:
                            wh_cfg = _parse_hours_config(client.working_hours) if client.working_hours else {}
                            next_slot = find_next_available_slot(
                                client.calendar_id,
                                client.google_credentials,
                                start_dt,
                                start_hour=wh_cfg.get("start_hour") or 9,
                                end_hour=wh_cfg.get("end_hour") or 18,
                                allowed_days=wh_cfg.get("days") or list(range(7)),
                            )
                            taken_label = (
                                f"{start_dt.day} {start_dt.strftime('%B')} "
                                f"at {start_dt.strftime('%I:%M %p').lstrip('0')}"
                            )
                            if next_slot:
                                alt_label = (
                                    f"{next_slot.day} {next_slot.strftime('%B %Y')} "
                                    f"at {next_slot.strftime('%I:%M %p').lstrip('0')}"
                                )
                                collected["_pending_slot"] = next_slot.isoformat()
                                conversation.collected = collected
                                db.commit()
                                logger.info(f"⚠️ Slot taken ({start_dt}), suggested: {next_slot}")
                                return (
                                    f"⚠️ Sorry, *{taken_label}* is already booked.\n\n"
                                    f"The next available slot is:\n"
                                    f"📅 *{alt_label}*\n\n"
                                    f"Reply *YES* to book this slot ✅ or *NO* to choose a different time ❌"
                                )
                            else:
                                logger.info(f"⚠️ Slot taken ({start_dt}), no alt found within 7 days")
                                return (
                                    f"⚠️ Sorry, *{taken_label}* is already booked and we have "
                                    f"no available slots in the next 7 days.\n\n"
                                    f"Please choose a different date or contact us at "
                                    f"{client.contact_phone or 'our office'} directly."
                                )

            # ── Finalise booking ───────────────────────────────────────────
            lead = Lead(
                client_id=client.id,
                phone=phone,
                data=conversation.collected,
                status="new",
            )
            db.add(lead)
            conversation.is_complete = True
            conversation.stage = "completed"
            db.commit()

            # Send confirmation email
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

            # Add to Google Sheets
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
            email_val = conversation.collected.get("email", "")
            service = conversation.collected.get("service_type", "")
            email_line = f"📧 Confirmation sent to {email_val}\n" if email_val else ""
            service_line = f"🎯 Service: *{service}*\n" if service else ""

            return (
                f"*🎉 You're all set, {name}!*\n\n"
                f"{service_line}"
                f"Our team at *{client.business_name}* will reach out shortly.\n\n"
                f"{email_line}"
                f"📞 Urgent? Call {client.contact_phone or 'us'}\n\n"
                f"_Thank you for choosing {client.business_name}. "
                f"Looking forward to working with you!_ 🚀"
            )

        # If user says NO to a suggested alt slot, keep the date — only clear time
        if is_no and "_pending_slot" in collected:
            collected.pop("_pending_slot", None)
            saved_date = (
                collected.get("date")
                or collected.get("appointment_date")
                or collected.get("preferred_time")
            )
            # Clear only time fields — preserve the date so "11 am" isn't mis-parsed as 11th
            for _f in ("time", "appointment_time"):
                if _f in fields:
                    collected.pop(_f, None)
            conversation.collected = collected
            conversation.stage = "collecting"
            db.commit()
            date_ctx = f" on *{saved_date}*" if saved_date else ""
            q_time = FIELD_QUESTIONS.get("time", "What time works best?")
            return f"No problem! What time would you prefer{date_ctx}?\n\n*{q_time}* 😊"

        # Change a specific field at confirm stage ("change name", "wrong email", etc.)
        answer = user_text.strip()
        change = _parse_change_intent(lower, answer, collected, fields)
        if change:
            field_to_change, inline_value = change
            if inline_value and _validate_field(field_to_change, inline_value):
                collected[field_to_change] = inline_value
                conversation.collected = collected
                db.commit()
                return f"Updated ✅\n\n{_build_summary(collected, fields)}"
            collected.pop(field_to_change, None)
            conversation.collected = collected
            conversation.stage = "collecting"
            db.commit()
            label = FIELD_LABELS.get(field_to_change, field_to_change.replace("_", " ").title())
            q = FIELD_QUESTIONS.get(field_to_change, f"What's your {field_to_change.replace('_', ' ')}?")
            return f"Sure! Let's fix your *{label}*.\n\n*{q}* 😊"

        if is_no:
            # Generic "no" — show summary and ask what to change
            return (
                f"No problem! Tell me what you'd like to change.\n\n"
                f"{_build_summary(collected, fields)}\n\n"
                f"_Reply with e.g. 'change name' or 'wrong email'_ ✏️"
            )

        # Answer questions at confirming stage
        if _is_question(lower):
            ai_answer = await get_ai_reply(
                history, user_text, system_prompt, client.groq_api_key,
                "Answer this question briefly in max 3 lines. Do NOT end with a question.",
            )
            return f"{ai_answer}\n\n───────────────────\nReply *YES* to confirm ✅  |  *NO* to edit ✏️"

        # ── Smart value detection at confirm stage ────────────────────────────
        # If the user typed a value that clearly belongs to a field (email, phone,
        # time, date), update it directly and show the refreshed summary.
        detected_edit = _detect_field_for_confirm_edit(answer, fields)
        if detected_edit and _validate_field(detected_edit, answer):
            old_val = collected.get(detected_edit, "")
            label = FIELD_LABELS.get(detected_edit, detected_edit.replace("_", " ").title())
            collected[detected_edit] = answer
            conversation.collected = collected
            db.commit()
            logger.info(f"✏️ Smart-updated {detected_edit} = {answer} at confirm stage")
            old_note = f"_(was: {old_val})_ " if old_val and old_val != answer else ""
            return f"Updated *{label}* {old_note}✅\n\n{_build_summary(collected, fields)}"

        return (
            "Please reply *YES* to confirm ✅ or *NO* to edit ✏️\n\n"
            "_Or say 'change name / wrong email / update date' to fix a specific field._"
        )

    # ── COMPLETED ─────────────────────────────────────────────────────────────
    if stage == "completed":
        return await get_ai_reply(
            history,
            user_text,
            system_prompt,
            client.groq_api_key,
            f"""The user has already booked. Answer any follow-up helpfully.
Do NOT restart the conversation or ask for details again.
For urgent matters: {client.contact_phone or "contact us directly"}.
Max 3 lines.""",
        )

    # ── FALLBACK ──────────────────────────────────────────────────────────────
    logger.warning(f"⚠️ Unknown stage '{stage}' — resetting to greeting")
    conversation.stage = "greeting"
    db.commit()
    return _build_welcome(client)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — MESSAGE BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_service_menu(client: Client) -> str:
    """Return the numbered service list. Returns empty string if none configured."""
    custom = list(client.services or [])
    if not custom:
        return ""
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
    lines = []
    for i, svc in enumerate(custom):
        emoji = emojis[i] if i < len(emojis) else "▪️"
        name = svc.get("name", "")
        lines.append(f"{emoji} {name}")
    return "\n".join(lines)


def _build_welcome(client: Client) -> str:
    menu = _build_service_menu(client)

    if menu:
        return (
            f"👋 *Hey! Welcome to {client.business_name}*\n\n"
            f"What can we help you with today?\n\n"
            f"{menu}\n\n"
            f"_Reply with a number_ 👆"
        )
    return (
        f"👋 *Hey! Welcome to {client.business_name}*\n\n"
        f"How can we help you today? 😊"
    )


def _build_summary(collected: dict, fields: list) -> str:
    """Build a clean confirmation summary showing only user-facing fields."""
    lines = []
    # Show service type first if present
    if collected.get("service_type"):
        lines.append(f"  🎯 *Service:* {collected['service_type']}")
    for key in fields:
        value = collected.get(key)
        if not value:
            continue
        label = FIELD_LABELS.get(key, key.replace("_", " ").title())
        lines.append(f"  ✦ *{label}:* {value}")

    summary = "\n".join(lines)
    return (
        f"*📋 Here's a summary of your details:*\n\n"
        f"{summary}\n\n"
        f"─────────────────────────\n"
        f"Is everything correct?\n\n"
        f"Reply *YES* to confirm ✅  |  *NO* to edit ✏️"
    )


def _transition_to_collecting(
    conversation: Conversation,
    fields: list,
    collected: dict,
    db: Session,
) -> str:
    """Move conversation to collecting stage and ask the first missing field."""
    conversation.stage = "collecting"
    db.commit()
    missing = [f for f in fields if not collected.get(f)]
    if not missing:
        conversation.stage = "confirming"
        db.commit()
        return _build_summary(collected, fields)
    first = missing[0]
    question = FIELD_QUESTIONS.get(first, f"Can you share your {first.replace('_', ' ')}?")
    return (
        "Awesome! 🙌 Let me get a few quick details so our team can reach out.\n\n"
        f"*{question}* 😊"
    )


def _get_ack() -> str:
    return "Perfect, noted! ✅"


def _build_progress(collected: dict, fields: list) -> str:
    """Compact progress: shows collected ✅ and missing ○ fields."""
    done, todo = [], []
    for f in fields:
        label = FIELD_LABELS.get(f, f.replace("_", " ").title())
        if collected.get(f):
            done.append(f"  ✅ *{label}:* {collected[f]}")
        else:
            todo.append(f"  ○ {label}")
    parts = []
    if done:
        parts.append("\n".join(done))
    if todo:
        parts.append("*Still needed:* " + ", ".join(
            FIELD_LABELS.get(f, f.replace("_", " ").title()) for f in fields if not collected.get(f)
        ))
    return "\n".join(parts)


def _detect_field_from_value(value: str, fields: list) -> str | None:
    """
    Auto-detect which field a value belongs to based on its format.
    Only detects fields with clear signatures (email, phone).
    """
    stripped = value.strip()

    # Email — has @ with a domain
    if "@" in stripped and "." in stripped.split("@")[-1] and "email" in fields:
        return "email"

    # Indian mobile — 10 digits starting 6-9, or +91/91 prefix
    digits = re.sub(r"\D", "", stripped)
    if len(digits) == 12 and digits[:2] == "91" and digits[2] in "6789":
        digits = digits[2:]
    if len(digits) == 10 and digits[0] in "6789" and "phone" in fields:
        return "phone"

    return None


def _detect_field_for_confirm_edit(value: str, fields: list) -> str | None:
    """
    Extended field detection used at the confirming stage so users can type a
    new value directly (e.g. '3pm', '5th June', new email) and have it
    auto-routed to the correct field.
    Priority: email → phone → time (pure) → date → preferred_time
    """
    stripped = value.strip()
    lower_v = stripped.lower()

    # Email
    if "@" in stripped and "." in stripped.split("@")[-1] and "email" in fields:
        return "email"

    # Indian mobile
    digits = re.sub(r"\D", "", stripped)
    if len(digits) == 12 and digits[:2] == "91" and digits[2] in "6789":
        digits = digits[2:]
    if len(digits) == 11 and digits[0] == "0":
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789" and "phone" in fields:
        return "phone"

    # Pure time ("3pm", "afternoon", "14:30") — no date tokens besides numbers
    if _PURE_TIME_RE.match(lower_v):
        if "time" in fields:
            return "time"
        if "preferred_time" in fields:
            return "preferred_time"

    # Date tokens (weekday names, month names, ordinals like "5th June")
    if _DATE_TOKENS.search(lower_v):
        if "date" in fields:
            return "date"
        if "preferred_time" in fields:
            return "preferred_time"

    return None


_CHANGE_TRIGGERS = re.compile(
    r"\b(change|update|edit|modify|correct|correction|wrong|mistake|actually|oops|fix|alter)\b",
    re.IGNORECASE,
)

_FIELD_KEYWORDS: dict[str, list[str]] = {
    "name":             ["name", "my name"],
    "email":            ["email", "mail", "e-mail", "gmail"],
    "phone":            ["phone", "number", "mobile", "cell", "contact"],
    "company":          ["company", "business", "firm", "organization", "org"],
    "budget":           ["budget", "price", "cost", "amount"],
    "date":             ["date", "day", "appointment", "schedule"],
    "time":             ["time", "slot", "timing"],
    "preferred_time":   ["time", "slot", "timing", "schedule"],
    "location":         ["location", "city", "address", "place"],
    "project_description": ["project", "description", "details"],
}


def _parse_change_intent(lower: str, original: str, collected: dict, fields: list) -> tuple[str, str] | None:
    """
    Detect if the user wants to change/correct a field.
    Returns (field_name, inline_new_value_or_empty) or None.

    Examples:
      "change my email"            → ("email", "")
      "actually my name is Rahul"  → ("name", "Rahul")
      "wrong number, it's 9876543210" → ("phone", "9876543210")
    """
    if not _CHANGE_TRIGGERS.search(lower):
        return None

    # Which field?
    target_field = None
    for field in fields:
        keywords = _FIELD_KEYWORDS.get(field, [field.replace("_", " ")])
        if any(kw in lower for kw in keywords):
            target_field = field
            break

    # Fallback: last collected field
    if not target_field:
        for field in reversed(fields):
            if collected.get(field):
                target_field = field
                break

    if not target_field:
        return None

    # Try to extract inline value: "change name to Rahul" / "actually email is x@y.com"
    m = re.search(r"\b(?:is|to|be|:)\s+(.+)$", lower)
    inline = m.group(1).strip() if m else ""

    return (target_field, inline)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — DETECTION & VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

_ORDINALS = {
    "first": 0, "1st": 0,
    "second": 1, "2nd": 1,
    "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3,
    "fifth": 4, "5th": 4,
    "sixth": 5, "6th": 5,
}


def _detect_services(lower: str, client_services: list | None = None) -> list[str]:
    """
    Detect all services the user selected.
    Understands: '1 and 3', 'first and second', 'everything', 'both',
                 service names, partial names, and number lists.
    """
    if not client_services:
        result = []
        if "website" in lower or "web" in lower:
            result.append("Website")
        if "brand" in lower:
            result.append("Branding")
        if "ai" in lower or "artificial" in lower or "automation" in lower:
            result.append("AI Integration")
        if "social" in lower or "instagram" in lower or "facebook" in lower:
            result.append("Social Media")
        return result

    all_names = [s.get("name", "") for s in client_services if s.get("name")]

    # "all", "everything", "both" (when 2 services) → all services
    if re.search(r"\b(all|everything|every|each)\b", lower):
        return all_names
    if "both" in lower and len(all_names) == 2:
        return all_names

    found = []

    # Ordinal words: "first", "second", "third" …
    for word, idx in _ORDINALS.items():
        if re.search(r"\b" + word + r"\b", lower) and idx < len(client_services):
            name = client_services[idx].get("name", "")
            if name and name not in found:
                found.append(name)

    # Numeric: "1 and 3", "1, 2", "1 2"
    numbers = re.findall(r"\b(\d+)\b", lower)
    for num_str in numbers:
        idx = int(num_str) - 1
        if 0 <= idx < len(client_services):
            name = client_services[idx].get("name", "")
            if name and name not in found:
                found.append(name)

    if found:
        return found

    # Name / keyword match
    for svc in client_services:
        name = svc.get("name", "")
        if not name:
            continue
        name_lower = name.lower()
        if name_lower in lower or name_lower == lower.strip():
            if name not in found:
                found.append(name)
        elif any(w in lower for w in name_lower.split() if len(w) > 3):
            if name not in found:
                found.append(name)

    return found


def _is_in_scope(text: str, service: str) -> bool:
    """Check if a message is within the scope of the selected service."""
    scope_words = SERVICE_SCOPE.get(service, [])
    return any(word in text for word in scope_words)


def _is_question(text: str) -> bool:
    """
    Check if the user's message is a question or follow-up inquiry.
    More permissive than _is_off_topic_for_field — used during qualification.
    """
    v = text.lower().strip()
    if v.endswith("?"):
        return True
    question_starters = (
        "what", "who", "why", "how", "when", "where", "which",
        "can you", "do you", "is it", "are you", "tell me",
        "explain", "describe", "i want to know", "what is",
        "what are", "how much", "how long",
    )
    return any(v.startswith(q) for q in question_starters)


_QUESTION_STARTERS = (
    "what", "who", "why", "how", "when", "where", "which",
    "can you", "do you", "is it", "are you", "tell me",
    "explain", "describe", "i want to know", "what is", "what are",
    "how much", "how long", "could you", "would you", "is there",
    "are there", "does it", "will you", "shall we", "should i",
    "i have a question", "i was wondering", "just wondering",
)

_NON_ANSWER_PHRASES = (
    "not sure", "don't know", "idk", "no idea", "not really",
    "let me think", "i'm not sure", "i don't know", "not yet",
    "can we skip", "i'll decide later", "no clue",
)

_DATE_TOKENS = re.compile(
    r"(?:"
    # Compact times like "2pm", "11am", "3:30pm" — digit glued to am/pm (no space)
    r"\d{1,2}(?::\d{2})?(?:am|pm)"
    r"|"
    # Day / month / keyword tokens (word-boundary safe)
    r"\b(?:mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday"
    r"|saturday|sunday|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
    r"|january|february|march|april|june|july|august|september|october"
    r"|november|december|today|tomorrow|next|morning|afternoon|evening"
    r"|night|noon|midnight|pm|am|\d{1,2}(?:st|nd|rd|th)?)\b"
    r")",
    re.IGNORECASE,
)

# Validates that a "time" field answer actually looks like a time
_TIME_SIGNAL_RE = re.compile(
    r"\d{1,2}(?:am|pm)"                              # "2pm", "11am" (compact)
    r"|\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b"          # "2 pm", "3:30 pm"
    r"|\b\d{1,2}:\d{2}\b"                            # "14:30", "2:30"
    r"|\b(?:morning|afternoon|evening|night|noon|midnight)\b"
    r"|\b\d{1,2}\b",                                  # bare hour like "2", "14"
    re.IGNORECASE,
)

# Pure time strings like "3pm", "3:30pm", "3 pm", "11am", "14:00" — no date info
_PURE_TIME_RE = re.compile(
    r"^(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?|morning|afternoon|evening|night|noon|midnight)$",
    re.IGNORECASE,
)

# Inline time token inside a combined "date + time" string
_INLINE_TIME_RE = re.compile(
    r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b"
    r"|\b(morning|afternoon|evening|night|noon|midnight)\b",
    re.IGNORECASE,
)


def _extract_time_str(text: str) -> str | None:
    """Return the time token from a combined date+time string, or None."""
    m = _INLINE_TIME_RE.search(text)
    if m:
        return (m.group(1) or m.group(2)).strip()
    return None


def _is_off_topic_for_field(value: str, current_field: str) -> bool:
    """
    Returns True when the user's message is clearly a question or conversational
    filler — not an actual answer to the field being collected.
    """
    v = value.lower().strip()

    if not v:
        return False

    # Hard signals: ends with ? or contains clear question/non-answer phrases
    if v.endswith("?"):
        return True

    if any(phrase in v for phrase in _NON_ANSWER_PHRASES):
        return True

    starts_with_question = any(v.startswith(q) for q in _QUESTION_STARTERS)

    if starts_with_question:
        if current_field in STRICT_FIELDS:
            return True
        # Loose fields: "when is next week" is a valid date — only flag clearly long questions
        if len(v.split()) > 4:
            return True

    # Name field — catch sentences masquerading as names (no ? needed)
    if current_field == "name":
        if re.search(
            r"\b(i\s+am|i'm|i\s+want|i\s+need|i\s+have|i\s+can"
            r"|it\s+is|it's|this\s+is|that\s+is|we\s+are|we're"
            r"|i\s+am\s+a|i\s+am\s+an|there\s+is|there\s+are)\b",
            v,
        ):
            return True
        if len(v.split()) > 5:  # real names are at most ~5 words
            return True

    # Date / time fields must contain date-like content; reject pure prose
    if current_field in {"date", "preferred_time", "time"}:
        if not _DATE_TOKENS.search(v):
            return True

    return False


def _validate_field(field: str, value: str) -> bool:
    """
    Validate a collected field value.
    Strict validation for email, phone, budget, name.
    Loose validation (any non-empty answer) for all others.
    """
    stripped = value.strip()
    if not stripped:
        return False

    value_lower = stripped.lower()

    # ── EMAIL ──────────────────────────────────────────────────────────────
    if field == "email":
        # Must have @ and a dot in the domain part
        if "@" not in value:
            return False
        domain = value.split("@")[-1]
        return "." in domain and len(domain) > 2

    # ── PHONE ──────────────────────────────────────────────────────────────
    if field == "phone":
        digits = re.sub(r"\D", "", value)
        # Strip country code +91 / 91
        if len(digits) == 12 and digits[:2] == "91":
            digits = digits[2:]
        if len(digits) == 11 and digits[0] == "0":
            digits = digits[1:]
        return len(digits) == 10 and digits[0] in "6789"

    # ── BUDGET ─────────────────────────────────────────────────────────────
    if field == "budget":
        has_number = any(c.isdigit() for c in value)
        budget_keywords = {
            "k", "l", "lakh", "lac", "thousand", "usd", "inr",
            "₹", "$", "cr", "crore", "million", "free", "discuss",
            "negotiable", "flexible", "open", "tbd",
        }
        has_currency = any(w in value_lower.split() or w in value_lower for w in budget_keywords)
        return has_number or has_currency

    # ── NAME ───────────────────────────────────────────────────────────────
    if field == "name":
        # Blocklist of clearly non-name words
        non_name_words = {
            "discuss", "meeting", "call", "schedule", "book",
            "yes", "no", "ok", "okay", "sure", "website", "service",
            "help", "need", "want", "hi", "hello", "hey", "lets",
            "can", "what", "how", "when", "where", "why", "which",
            "blackhole", "google", "internet", "computer", "phone",
            "anything", "something", "everything", "nothing", "idk",
            "dunno", "maybe", "perhaps",
        }
        if value_lower in non_name_words:
            return False

        # Names are at most 5 words — longer inputs are sentences, not names
        if len(stripped.split()) > 5:
            return False

        # Sentence patterns like "it is a ...", "this is a ..." are not names
        if re.search(
            r"\b(it\s+is|it's|this\s+is|that\s+is|i\s+am|i'm|we\s+are|we're|there\s+is)\b",
            value_lower,
        ):
            return False

        # Must have at least some letters and be at least 2 chars
        has_letters = any(c.isalpha() for c in stripped)
        return has_letters and len(stripped) >= 2

    # ── TIME ───────────────────────────────────────────────────────────────
    # Must contain an actual time signal — rejects date-only inputs like "4th June"
    if field == "time":
        return bool(_TIME_SIGNAL_RE.search(stripped))

    # ── DATE / LOOSE FIELDS ────────────────────────────────────────────────
    # Accept any answer with at least 2 characters of content
    return len(stripped) >= 2


def _resolve_slot_dt(collected: dict):
    """
    Parse date + time from collected data into a timezone-aware datetime (IST).
    Returns (start_dt, end_dt) tuple or (None, None) if parsing fails.
    """
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
    raw_date = (
        collected.get("date")
        or collected.get("preferred_time")
        or collected.get("appointment_date")
    )
    raw_time = collected.get("time") or collected.get("appointment_time")
    date_dt = _cal_parse_date(raw_date)
    time_hm = _cal_parse_time(raw_time)
    if not date_dt:
        return None, None
    hour, minute = time_hm if time_hm else (10, 0)
    from datetime import timedelta
    start_dt = date_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    end_dt = start_dt + timedelta(minutes=30)
    return start_dt, end_dt


def _parse_hours_config(working_hours: str) -> dict:
    """Parse a working hours string into {days: [weekday ints], start_hour, end_hour}."""
    wh = working_hours.lower().strip()
    DAY_MAP = {
        "mon": 0, "monday": 0,
        "tue": 1, "tuesday": 1,
        "wed": 2, "wednesday": 2,
        "thu": 3, "thursday": 3,
        "fri": 4, "friday": 4,
        "sat": 5, "saturday": 5,
        "sun": 6, "sunday": 6,
    }

    # Extract time range — "10am-6pm", "9:00am - 9:00pm", "10 am to 6 pm"
    tm = re.search(
        r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*[-–to\s]+\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)", wh
    )
    start_h = end_h = None
    if tm:
        sh, _, sap, eh, _, eap = tm.groups()
        start_h = int(sh)
        if sap == "pm" and start_h != 12:
            start_h += 12
        elif sap == "am" and start_h == 12:
            start_h = 0
        end_h = int(eh)
        if eap == "pm" and end_h != 12:
            end_h += 12
        elif eap == "am" and end_h == 12:
            end_h = 0

    # Extract day range — "mon-sat", "monday to friday"
    dm = re.search(
        r"(mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
        r"\s*[-–to\s]+\s*"
        r"(mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)",
        wh,
    )
    days = list(range(7))
    if dm:
        sd = DAY_MAP.get(dm.group(1)[:3])
        ed = DAY_MAP.get(dm.group(2)[:3])
        if sd is not None and ed is not None:
            days = list(range(sd, ed + 1)) if sd <= ed else list(range(sd, 7)) + list(range(0, ed + 1))

    return {"days": days, "start_hour": start_h, "end_hour": end_h}


def _is_within_working_hours(user_answer: str, working_hours: str) -> bool:
    """
    Deterministic working hours check. Returns False only when clearly outside.
    Fails open (returns True) when parsing is ambiguous.
    """
    try:
        from services.calendar_service import _parse_date, _parse_time
        config = _parse_hours_config(working_hours)
        text = user_answer.lower().strip()

        # Check requested time against business hours
        if config["start_hour"] is not None and config["end_hour"] is not None:
            t = _parse_time(text)
            if t:
                hour = t[0]
                # Use <= for end_hour so "6pm" is valid when hours end at 6pm
                if not (config["start_hour"] <= hour <= config["end_hour"]):
                    return False

        # Check requested day against working days.
        # Skip if the input is a pure time (e.g. "3pm") — no day info, so don't
        # let _parse_date misread "3" as "the 3rd of next month".
        if config["days"] != list(range(7)) and not _PURE_TIME_RE.match(text):
            d = _parse_date(text)
            if d and d.weekday() not in config["days"]:
                return False

        return True
    except Exception:
        return True  # fail open


def _get_field_hint(field: str) -> str:
    """Return a user-friendly hint for invalid field answers."""
    hints = {
        "email": "Please enter a valid email _(e.g. john@example.com)_\n\n",
        "phone": "Please enter a valid 10-digit Indian mobile number _(starting with 6, 7, 8 or 9)_\n\n",
        "budget": "Please mention a budget _(e.g. ₹50,000 or $500 or 'flexible')_\n\n",
        "name": "Please enter your full name _(e.g. Rahul Sharma)_\n\n",
        "date": "Please mention a date _(e.g. Monday, 3rd June, next week)_\n\n",
        "time": "Please mention a time _(e.g. 2pm, 3:30pm, afternoon)_\n\n",
    }
    return hints.get(field, "")
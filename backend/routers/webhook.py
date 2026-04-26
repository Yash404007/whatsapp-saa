from fastapi import APIRouter, Request, Query, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.client import Client
from services.whatsapp_service import send_message, parse_incoming
from services.bot_engine import process_message
from loguru import logger

router = APIRouter()


@router.get("")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    db: Session = Depends(get_db)
):
    """Meta webhook verification."""
    client = db.query(Client).filter(
        Client.wa_verify_token == hub_verify_token
    ).first()

    if hub_mode == "subscribe" and client:
        logger.success(f"✅ Webhook verified for {client.business_name}")
        return int(hub_challenge)

    return {"status": "forbidden"}


@router.post("")
async def receive_message(request: Request, db: Session = Depends(get_db)):
    """Receive and process incoming WhatsApp messages."""
    data = await request.json()

    # Parse incoming message
    phone, text, phone_number_id = parse_incoming(data)

    if not phone or not text or not phone_number_id:
        return {"status": "ok"}

    logger.info(f"📩 INCOMING {phone} → {text}")

    # Find client by WhatsApp phone number ID
    client = db.query(Client).filter(
        Client.wa_phone_id == phone_number_id,
        Client.is_active == True
    ).first()

    if not client:
        logger.warning(f"⚠️ No client found for phone_number_id: {phone_number_id}")
        return {"status": "ok"}

    # Process message through bot engine
    reply = await process_message(phone, text, client, db)

    logger.info(f"📤 OUTGOING {phone} ← {reply[:60]}...")

    # Send reply via WhatsApp
    await send_message(phone, reply, client.wa_access_token, client.wa_phone_id)

    return {"status": "ok"}
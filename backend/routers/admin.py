from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models.client import Client
from models.conversation import Conversation, Lead
from pydantic import BaseModel
from typing import Optional, List
from services.ai_service import generate_system_prompt
from services.google_setup_service import setup_google_for_client
from config import settings
from loguru import logger
import uuid

router = APIRouter()


class ClientCreate(BaseModel):
    business_name: str
    business_type: str
    description: str
    bot_name: Optional[str] = "Alex"
    bot_tone: Optional[str] = "friendly"
    working_hours: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    collect_fields: Optional[List[str]] = []
    services: Optional[List[dict]] = None
    wa_phone_id: Optional[str] = None
    wa_access_token: Optional[str] = None
    wa_verify_token: Optional[str] = None
    use_calendar: Optional[bool] = False
    use_sheets: Optional[bool] = False
    use_email: Optional[bool] = False
    google_credentials: Optional[dict] = None
    gmail_sender: Optional[str] = None
    gmail_password: Optional[str] = None
    google_account_email: Optional[str] = None
    groq_api_key: Optional[str] = None
    dashboard_username: Optional[str] = None
    dashboard_password: Optional[str] = None


class ClientUpdate(BaseModel):
    wa_phone_id: Optional[str] = None
    wa_access_token: Optional[str] = None
    wa_verify_token: Optional[str] = None
    groq_api_key: Optional[str] = None
    is_active: Optional[bool] = None
    working_hours: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    address: Optional[str] = None
    bot_name: Optional[str] = None
    bot_tone: Optional[str] = None
    description: Optional[str] = None
    collect_fields: Optional[List[str]] = None
    services: Optional[List[dict]] = None
    gmail_sender: Optional[str] = None
    gmail_password: Optional[str] = None
    google_account_email: Optional[str] = None
    use_email: Optional[bool] = None
    use_calendar: Optional[bool] = None
    use_sheets: Optional[bool] = None
    google_credentials: Optional[dict] = None
    dashboard_username: Optional[str] = None
    dashboard_password: Optional[str] = None
    sheets_id: Optional[str] = None
    calendar_id: Optional[str] = None
   


@router.get("/clients")
def get_all_clients(db: Session = Depends(get_db)):
    clients = db.query(Client).all()
    return [
        {
            "id": str(c.id),
            "business_name": c.business_name,
            "business_type": c.business_type,
            "bot_name": c.bot_name,
            "is_active": c.is_active,
            "created_at": str(c.created_at),
        }
        for c in clients
    ]


def _build_oauth() -> dict | None:
    if settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET and settings.GOOGLE_OAUTH_REFRESH_TOKEN:
        return {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "refresh_token": settings.GOOGLE_OAUTH_REFRESH_TOKEN,
        }
    return None


def _run_google_setup(client_id: str):
    """Auto-provision Google Sheet + Calendar — uses its own DB session to avoid thread-safety issues."""
    sa_json = settings.GOOGLE_SERVICE_ACCOUNT_JSON
    admin_email = settings.GOOGLE_ADMIN_EMAIL
    if not sa_json or not admin_email:
        return

    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            return

        # Share to per-bot Gmail if set, otherwise fall back to master admin email
        share_emails = [admin_email]
        if client.google_account_email and client.google_account_email != admin_email:
            share_emails.append(client.google_account_email)

        result = setup_google_for_client(client.business_name, share_emails, sa_json, oauth=_build_oauth())
        if result:
            if "sheets_id" in result:
                client.sheets_id = result["sheets_id"]
                client.google_credentials = sa_json
                client.use_sheets = True
            if "calendar_id" in result:
                client.calendar_id = result["calendar_id"]
                client.google_credentials = sa_json
                client.use_calendar = True
            db.commit()
            logger.success(f"✅ Google auto-setup done for {client.business_name} → shared to {share_emails}")
    except Exception as e:
        logger.error(f"❌ Google setup background error: {e}")
        db.rollback()
    finally:
        db.close()


@router.post("/clients")
def create_client(data: ClientCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        system_prompt = generate_system_prompt(data.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to generate system prompt: {str(e)}")

    client = Client(
        id=uuid.uuid4(),
        system_prompt=system_prompt,
        **data.dict()
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    # Auto-create Google Sheet + Calendar in background (own session)
    background_tasks.add_task(_run_google_setup, str(client.id))

    return {
        "message": "Client created successfully",
        "client_id": str(client.id),
        "system_prompt": system_prompt
    }


@router.post("/clients/{client_id}/setup-google")
def setup_google(client_id: str, db: Session = Depends(get_db)):
    """Manually trigger Google Sheet + Calendar setup for an existing client."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    sa_json = settings.GOOGLE_SERVICE_ACCOUNT_JSON
    admin_email = settings.GOOGLE_ADMIN_EMAIL
    if not sa_json or not admin_email:
        raise HTTPException(status_code=400, detail="GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_ADMIN_EMAIL not set in .env")

    share_emails = [admin_email]
    if client.google_account_email and client.google_account_email != admin_email:
        share_emails.append(client.google_account_email)

    result = setup_google_for_client(client.business_name, share_emails, sa_json, oauth=_build_oauth())
    if not result:
        raise HTTPException(status_code=500, detail="Google setup failed — check server logs")

    if "sheets_id" in result:
        client.sheets_id = result["sheets_id"]
        client.google_credentials = sa_json
        client.use_sheets = True
    if "calendar_id" in result:
        client.calendar_id = result["calendar_id"]
        client.google_credentials = sa_json
        client.use_calendar = True
    db.commit()

    return {"message": "Google setup complete", **result}


@router.post("/setup-google-all")
def setup_google_all(db: Session = Depends(get_db)):
    """Run Google setup for all clients that don't have sheets/calendar yet."""
    sa_json = settings.GOOGLE_SERVICE_ACCOUNT_JSON
    admin_email = settings.GOOGLE_ADMIN_EMAIL
    if not sa_json or not admin_email:
        raise HTTPException(status_code=400, detail="GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_ADMIN_EMAIL not set in .env")

    clients = db.query(Client).all()
    done, skipped, failed = [], [], []

    for client in clients:
        needs_sheets   = not client.sheets_id
        needs_calendar = not client.calendar_id
        if not needs_sheets and not needs_calendar:
            skipped.append(client.business_name)
            continue

        share_emails = [admin_email]
        if client.google_account_email and client.google_account_email != admin_email:
            share_emails.append(client.google_account_email)

        result = setup_google_for_client(client.business_name, share_emails, sa_json, oauth=_build_oauth())
        if result:
            if "sheets_id" in result:
                client.sheets_id = result["sheets_id"]
                client.google_credentials = sa_json
                client.use_sheets = True
            if "calendar_id" in result:
                client.calendar_id = result["calendar_id"]
                client.google_credentials = sa_json
                client.use_calendar = True
            db.commit()
            done.append(client.business_name)
        else:
            failed.append(client.business_name)

    return {"done": done, "skipped": skipped, "failed": failed}


@router.get("/clients/{client_id}")
def get_client(client_id: str, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return {
        "id": str(client.id),
        "business_name": client.business_name,
        "business_type": client.business_type,
        "description": client.description,
        "bot_name": client.bot_name,
        "bot_tone": client.bot_tone,
        "working_hours": client.working_hours,
        "contact_phone": client.contact_phone,
        "system_prompt": client.system_prompt,
        "collect_fields": client.collect_fields,
        "services": client.services,
        "use_calendar": client.use_calendar,
        "use_sheets": client.use_sheets,
        "use_email": client.use_email,
        "gmail_sender": client.gmail_sender,
        "gmail_password": "***" if client.gmail_password else None,
        "google_account_email": client.google_account_email,
        "wa_phone_id": client.wa_phone_id,
        "wa_access_token": "***" if client.wa_access_token else None,
        "groq_api_key": "***" if client.groq_api_key else None,
        "is_active": client.is_active,
        "created_at": str(client.created_at),
        "sheets_id": client.sheets_id,
        "calendar_id": client.calendar_id,
    }


@router.put("/clients/{client_id}")
def update_client(client_id: str, data: ClientUpdate, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for key, value in data.dict(exclude_none=True).items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return {"message": "Client updated successfully"}


@router.put("/clients/{client_id}/regenerate-prompt")
def regenerate_prompt(client_id: str, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    try:
        system_prompt = generate_system_prompt({
            "business_name": client.business_name,
            "business_type": client.business_type,
            "description": client.description,
            "bot_name": client.bot_name,
            "bot_tone": client.bot_tone,
            "working_hours": client.working_hours,
            "contact_phone": client.contact_phone,
            "address": client.address,
            "collect_fields": client.collect_fields,
            "groq_api_key": client.groq_api_key,
        })
        client.system_prompt = system_prompt
        db.commit()
        return {"message": "Prompt regenerated", "system_prompt": system_prompt}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/clients/{client_id}")
def delete_client(client_id: str, db: Session = Depends(get_db)):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.query(Lead).filter(Lead.client_id == client_id).delete()
    db.query(Conversation).filter(Conversation.client_id == client_id).delete()
    db.delete(client)
    db.commit()
    return {"message": "Client deleted successfully"}
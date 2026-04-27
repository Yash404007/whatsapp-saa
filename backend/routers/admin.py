from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.client import Client
from pydantic import BaseModel
from typing import Optional, List
from services.ai_service import generate_system_prompt
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
    wa_phone_id: Optional[str] = None
    wa_access_token: Optional[str] = None
    wa_verify_token: Optional[str] = None
    use_calendar: Optional[bool] = False
    use_sheets: Optional[bool] = False
    use_email: Optional[bool] = False
    google_credentials: Optional[dict] = None
    gmail_sender: Optional[str] = None
    gmail_password: Optional[str] = None
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
    gmail_sender: Optional[str] = None
    gmail_password: Optional[str] = None
    use_email: Optional[bool] = None
    use_calendar: Optional[bool] = None
    use_sheets: Optional[bool] = None
    google_credentials: Optional[dict] = None
    dashboard_username: Optional[str] = None
    dashboard_password: Optional[str] = None


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


@router.post("/clients")
def create_client(data: ClientCreate, db: Session = Depends(get_db)):
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

    return {
        "message": "Client created successfully",
        "client_id": str(client.id),
        "system_prompt": system_prompt
    }


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
        "use_calendar": client.use_calendar,
        "use_sheets": client.use_sheets,
        "use_email": client.use_email,
        "gmail_sender": client.gmail_sender,
        "gmail_password": "***" if client.gmail_password else None,
        "wa_phone_id": client.wa_phone_id,
        "wa_access_token": "***" if client.wa_access_token else None,
        "groq_api_key": "***" if client.groq_api_key else None,
        "is_active": client.is_active,
        "created_at": str(client.created_at),
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
    db.delete(client)
    db.commit()
    return {"message": "Client deleted successfully"}
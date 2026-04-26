from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.client import Client
from models.conversation import Lead, Conversation

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "Dashboard router is running ✅"}


@router.post("/login")
def client_login(username: str, password: str, db: Session = Depends(get_db)):
    client = db.query(Client).filter(
        Client.dashboard_username == username,
        Client.dashboard_password == password,
        Client.is_active == True
    ).first()

    if not client:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "client_id": str(client.id),
        "business_name": client.business_name,
        "bot_name": client.bot_name,
    }


@router.get("/{client_id}/leads")
def get_leads(client_id: str, db: Session = Depends(get_db)):
    leads = db.query(Lead).filter(
        Lead.client_id == client_id
    ).order_by(Lead.created_at.desc()).all()

    return [
        {
            "id": str(l.id),
            "phone": l.phone,
            "data": l.data,
            "status": l.status,
            "created_at": str(l.created_at),
        }
        for l in leads
    ]


@router.get("/{client_id}/conversations")
def get_conversations(client_id: str, db: Session = Depends(get_db)):
    conversations = db.query(Conversation).filter(
        Conversation.client_id == client_id
    ).order_by(Conversation.updated_at.desc()).limit(50).all()

    return [
        {
            "id": str(c.id),
            "phone": c.phone,
            "stage": c.stage,
            "is_complete": c.is_complete,
            "message_count": len(c.history or []),
            "updated_at": str(c.updated_at),
        }
        for c in conversations
    ]


@router.get("/{client_id}/stats")
def get_stats(client_id: str, db: Session = Depends(get_db)):
    total_leads = db.query(Lead).filter(Lead.client_id == client_id).count()
    total_conversations = db.query(Conversation).filter(
        Conversation.client_id == client_id
    ).count()
    completed = db.query(Conversation).filter(
        Conversation.client_id == client_id,
        Conversation.is_complete == True
    ).count()

    return {
        "total_leads": total_leads,
        "total_conversations": total_conversations,
        "completed_conversations": completed,
    }
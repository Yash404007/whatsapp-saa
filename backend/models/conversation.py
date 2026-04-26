from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id    = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    phone        = Column(String, nullable=False)
    stage        = Column(String, default="greeting")
    history      = Column(JSON, default=list)
    collected    = Column(JSON, default=dict)
    is_complete  = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Lead(Base):
    __tablename__ = "leads"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id    = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    phone        = Column(String, nullable=False)
    data         = Column(JSON, default=dict)
    status       = Column(String, default="new")
    created_at   = Column(DateTime, default=datetime.utcnow)
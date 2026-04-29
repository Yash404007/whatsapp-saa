from sqlalchemy import Column, String, Boolean, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from database import Base


class Client(Base):
    __tablename__ = "clients"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_name    = Column(String, nullable=False)
    business_type    = Column(String, nullable=False)
    description      = Column(Text, nullable=False)
    bot_name         = Column(String, default="Priya")
    bot_tone         = Column(String, default="friendly")
    working_hours    = Column(String, nullable=True)
    contact_phone    = Column(String, nullable=True)
    contact_email    = Column(String, nullable=True)
    address          = Column(String, nullable=True)

    # AI generated system prompt
    system_prompt    = Column(Text, nullable=True)

    # Fields to collect from users
    collect_fields   = Column(JSON, default=list)

    # WhatsApp credentials
    wa_phone_id      = Column(String, nullable=True)
    wa_access_token  = Column(String, nullable=True)
    wa_verify_token  = Column(String, nullable=True)

    # Integrations
    use_calendar     = Column(Boolean, default=False)
    use_sheets       = Column(Boolean, default=False)
    use_email        = Column(Boolean, default=False)

    # Google credentials (stored as JSON)
    google_credentials = Column(JSON, nullable=True)

    # Gmail SMTP
    gmail_sender     = Column(String, nullable=True)
    gmail_password   = Column(String, nullable=True)

    #sheets
    sheets_id = Column(String, nullable=True)
    calendar_id = Column(String, nullable=True)

    # Groq API key
    groq_api_key     = Column(String, nullable=True)

    # Dashboard login
    dashboard_username = Column(String, nullable=True)
    dashboard_password = Column(String, nullable=True)

    # Status
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
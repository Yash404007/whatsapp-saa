import os
import json
from dotenv import load_dotenv

load_dotenv()

class Settings:
    ADMIN_SECRET_KEY: str = os.getenv("ADMIN_SECRET_KEY", "supersecretkey")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5433/whatsapp_saas")

    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

    # Master Google Service Account — used for Calendar creation
    GOOGLE_ADMIN_EMAIL: str = os.getenv("GOOGLE_ADMIN_EMAIL", "")
    _sa_raw: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    GOOGLE_SERVICE_ACCOUNT_JSON: dict = json.loads(_sa_raw) if _sa_raw else {}

    # OAuth credentials for the admin Gmail — used to create Google Sheets (service accounts have 0 Drive quota)
    GOOGLE_OAUTH_CLIENT_ID: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    GOOGLE_OAUTH_REFRESH_TOKEN: str = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", "")

settings = Settings()
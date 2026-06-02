from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS google_account_email VARCHAR"))
    conn.commit()

print("Migration done: 'google_account_email' column added.")

from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS services JSONB"))
    conn.commit()

print("Migration done: 'services' column added.")

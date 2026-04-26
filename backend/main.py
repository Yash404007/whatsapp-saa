from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine
from routers import admin, webhook, dashboard
from loguru import logger

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="WhatsApp SaaS Platform",
    description="Multi-tenant WhatsApp AI Bot Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router,     prefix="/admin",     tags=["Admin"])
app.include_router(webhook.router,   prefix="/webhook",   tags=["Webhook"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])


@app.get("/")
def root():
    return {"status": "WhatsApp SaaS Platform is running 🚀"}


@app.on_event("startup")
async def startup():
    logger.success("✅ Server started — all tables created")
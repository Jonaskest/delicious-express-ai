from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import analytics, assistant, menu, orders
from app.seed import seed_database

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Sistema inteligente de delivery evoluído em FastAPI + SQLAlchemy + Google Gemini AI + "
        "notificações Telegram + painel analítico em Pandas."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(assistant.router)
app.include_router(analytics.router)


@app.get("/api/health", tags=["Sistema"])
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "ai_mode": "gemini" if settings.ai_enabled else "demo_offline",
        "telegram_mode": "live" if settings.telegram_enabled else "simulated",
    }


@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse(STATIC_DIR / "index.html")

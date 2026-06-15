from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.rag.schemas import HealthResponse
from app.rag import service

router = APIRouter()


@router.get("/", tags=["meta"])
async def home():
    return {"service": "Last Mile Health RAG API", "status": "ok"}


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    llm_ok = service.check_llm_connection()

    return HealthResponse(
        status="ok" if db_ok and llm_ok else "degraded",
        database=db_ok,
        llm=llm_ok,
        llm_provider=settings.llm_provider,
    )
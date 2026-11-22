from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AssistantRequest, AssistantResponse
from app.services.ai_assistant import process_assistant_message

router = APIRouter(prefix="/api/assistant", tags=["Assistente IA"])


@router.post("/parse", response_model=AssistantResponse)
async def parse_order(payload: AssistantRequest, db: Session = Depends(get_db)):
    return await process_assistant_message(
        db,
        message=payload.message,
        auto_create=payload.auto_create,
    )

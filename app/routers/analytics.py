from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AnalyticsSummary
from app.services import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["Analytics & BI"])


@router.get("/summary", response_model=AnalyticsSummary)
def get_summary(db: Session = Depends(get_db)):
    return analytics_service.get_analytics_summary(db)


@router.get("/export.csv")
def export_csv(db: Session = Depends(get_db)):
    csv_content = analytics_service.export_orders_csv(db)
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="delicious_express_pedidos.csv"'},
    )

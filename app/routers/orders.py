from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import OrderCreate, OrderOut, OrderStatusUpdate
from app.services import order_service

router = APIRouter(prefix="/api/orders", tags=["Pedidos"])


@router.get("", response_model=list[OrderOut])
def list_orders(status_filter: str | None = None, db: Session = Depends(get_db)):
    return order_service.list_orders(db, status_filter=status_filter)


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    return await order_service.create_order(db, payload)


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_status(order_id: int, payload: OrderStatusUpdate, db: Session = Depends(get_db)):
    return order_service.update_order_status(db, order_id, payload.status)

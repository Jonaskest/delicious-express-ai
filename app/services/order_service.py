from collections import defaultdict
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models import Order, OrderItem, Product
from app.schemas import OrderCreate
from app.services.telegram_service import send_order_notification

ALLOWED_TRANSITIONS = {
    "recebido": {"em_preparo", "cancelado"},
    "em_preparo": {"saiu_para_entrega", "cancelado"},
    "saiu_para_entrega": {"entregue", "cancelado"},
    "entregue": set(),
    "cancelado": set(),
}


async def create_order(db: Session, payload: OrderCreate) -> Order:
    # Consolidate duplicate product_ids
    merged_qty: dict[int, int] = defaultdict(int)
    for item in payload.items:
        merged_qty[item.product_id] += item.quantity

    product_ids = list(merged_qty.keys())
    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    product_map = {p.id: p for p in products}

    missing = [pid for pid in product_ids if pid not in product_map]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto(s) não encontrado(s): {missing}",
        )

    unavailable = [p.name for p in products if not p.available]
    if unavailable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Produto(s) indisponível(is) no momento: {', '.join(unavailable)}",
        )

    order = Order(
        customer_name=payload.customer_name.strip(),
        customer_phone=payload.customer_phone.strip() if payload.customer_phone else None,
        delivery_address=payload.delivery_address.strip(),
        payment_method=payload.payment_method,
        notes=payload.notes.strip() if payload.notes else None,
        channel=payload.channel,
        status="recebido",
        total_amount=0.0,
    )

    total = 0.0
    for pid, qty in merged_qty.items():
        prod = product_map[pid]
        subtotal = round(prod.price * qty, 2)
        total += subtotal
        order.items.append(
            OrderItem(
                product_id=prod.id,
                product_name=prod.name,
                unit_price=prod.price,
                quantity=qty,
                subtotal=subtotal,
            )
        )

    order.total_amount = round(total, 2)
    db.add(order)
    db.commit()
    db.refresh(order)

    await send_order_notification(db, order)

    return (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.notifications))
        .filter(Order.id == order.id)
        .first()
    )


def list_orders(db: Session, status_filter: str | None = None) -> list[Order]:
    query = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.notifications))
        .order_by(Order.id.desc())
    )
    if status_filter:
        query = query.filter(Order.status == status_filter)
    return query.all()


def update_order_status(db: Session, order_id: int, new_status: str) -> Order:
    order = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.notifications))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")

    if order.status == new_status:
        return order

    allowed = ALLOWED_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transição inválida de '{order.status}' para '{new_status}'.",
        )

    order.status = new_status
    db.commit()
    db.refresh(order)
    return order

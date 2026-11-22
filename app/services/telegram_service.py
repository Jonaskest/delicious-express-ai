import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import NotificationLog, Order


def format_order_message(order: Order) -> str:
    items_lines = "\n".join(
        f"• {item.quantity}x {item.product_name} — R$ {item.subtotal:.2f}"
        for item in order.items
    )
    channel_label = "Assistente IA" if order.channel == "ai_chat" else "Cardápio Web"
    notes_line = f"\nObs.: {order.notes}" if order.notes else ""
    return (
        f"🍕 Novo Pedido #{order.id} — Delicious Express\n"
        f"Cliente: {order.customer_name}\n"
        f"Endereço: {order.delivery_address}\n"
        f"Canal: {channel_label} | Pagamento: {order.payment_method}\n\n"
        f"Itens:\n{items_lines}\n\n"
        f"Total: R$ {order.total_amount:.2f}{notes_line}"
    )


async def send_order_notification(db: Session, order: Order) -> NotificationLog:
    message = format_order_message(order)

    if settings.telegram_enabled:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": settings.telegram_chat_id,
            "text": message,
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                mode = "live"
                detail = "Mensagem enviada com sucesso via Telegram Bot API."
            else:
                mode = "error"
                detail = f"Telegram API retornou HTTP {resp.status_code}: {resp.text[:160]}"
        except Exception as exc:
            mode = "error"
            detail = f"Falha ao conectar na Telegram API: {str(exc)[:160]}"
    else:
        mode = "simulated"
        detail = "Modo local: TELEGRAM_BOT_TOKEN não configurado; payload auditado no banco."

    log = NotificationLog(
        order_id=order.id,
        channel="telegram",
        mode=mode,
        message=message,
        status_detail=detail,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

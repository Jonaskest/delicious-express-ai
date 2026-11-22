import io
import pandas as pd
from sqlalchemy.orm import Session, joinedload

from app.models import Order
from app.schemas import AnalyticsSummary, TopProductStat


def get_analytics_summary(db: Session) -> AnalyticsSummary:
    orders = db.query(Order).options(joinedload(Order.items)).all()

    if not orders:
        return AnalyticsSummary(
            total_orders=0,
            valid_orders=0,
            canceled_orders=0,
            total_revenue=0.0,
            average_ticket=0.0,
            orders_by_status={},
            orders_by_channel={},
            orders_by_payment={},
            top_products=[],
        )

    order_rows = [
        {
            "order_id": o.id,
            "status": o.status,
            "channel": o.channel,
            "payment_method": o.payment_method,
            "total_amount": o.total_amount,
        }
        for o in orders
    ]
    df_orders = pd.DataFrame(order_rows)

    valid_df = df_orders[df_orders["status"] != "cancelado"]
    total_orders = int(len(df_orders))
    valid_orders = int(len(valid_df))
    canceled_orders = total_orders - valid_orders
    total_revenue = round(float(valid_df["total_amount"].sum()), 2) if valid_orders else 0.0
    average_ticket = round(total_revenue / valid_orders, 2) if valid_orders else 0.0

    item_rows = [
        {
            "product_name": item.product_name,
            "quantity": item.quantity,
            "subtotal": item.subtotal,
        }
        for o in orders
        if o.status != "cancelado"
        for item in o.items
    ]

    top_products: list[TopProductStat] = []
    if item_rows:
        df_items = pd.DataFrame(item_rows)
        grouped = (
            df_items.groupby("product_name", as_index=False)
            .agg(quantity_sold=("quantity", "sum"), revenue=("subtotal", "sum"))
            .sort_values(by=["revenue", "quantity_sold"], ascending=False)
        )
        for row in grouped.itertuples(index=False):
            top_products.append(
                TopProductStat(
                    product_name=str(row.product_name),
                    quantity_sold=int(row.quantity_sold),
                    revenue=round(float(row.revenue), 2),
                )
            )

    return AnalyticsSummary(
        total_orders=total_orders,
        valid_orders=valid_orders,
        canceled_orders=canceled_orders,
        total_revenue=total_revenue,
        average_ticket=average_ticket,
        orders_by_status={str(k): int(v) for k, v in df_orders["status"].value_counts().items()},
        orders_by_channel={str(k): int(v) for k, v in df_orders["channel"].value_counts().items()},
        orders_by_payment={str(k): int(v) for k, v in df_orders["payment_method"].value_counts().items()},
        top_products=top_products,
    )


def export_orders_csv(db: Session) -> str:
    orders = db.query(Order).options(joinedload(Order.items)).order_by(Order.id.desc()).all()
    rows = []
    for o in orders:
        for item in o.items:
            rows.append(
                {
                    "pedido_id": o.id,
                    "data_utc": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
                    "cliente": o.customer_name,
                    "endereco": o.delivery_address,
                    "canal": o.channel,
                    "pagamento": o.payment_method,
                    "status": o.status,
                    "produto": item.product_name,
                    "quantidade": item.quantity,
                    "preco_unitario": item.unit_price,
                    "subtotal": item.subtotal,
                    "total_pedido": o.total_amount,
                }
            )

    df = pd.DataFrame(
        rows,
        columns=[
            "pedido_id", "data_utc", "cliente", "endereco", "canal", "pagamento",
            "status", "produto", "quantidade", "preco_unitario", "subtotal", "total_pedido",
        ],
    )
    buf = io.StringIO()
    # UTF-8 with BOM so Portuguese accents open cleanly in Excel
    buf.write("\ufeff")
    df.to_csv(buf, index=False, sep=";")
    return buf.getvalue()

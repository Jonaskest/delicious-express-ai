from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Product

INITIAL_PRODUCTS = [
    {
        "name": "Pizza Artesanal Margherita",
        "category": "Pizzas",
        "description": "Massa artesanal de fermentação lenta, molho de tomate pelati, mussarela e manjericão fresco.",
        "price": 45.00,
        "image_url": "/static/images/pizza_margherita.jpg",
    },
    {
        "name": "Pizza Calabresa Especial",
        "category": "Pizzas",
        "description": "Calabresa fatiada, cebola roxa caramelizada, mussarela e orégano.",
        "price": 48.00,
        "image_url": "/static/images/pizza_calabresa.jpg",
    },
    {
        "name": "Açaí na Tigela 500ml",
        "category": "Açaí",
        "description": "Açaí cremoso batido na hora com granola crocante, banana e leite condensado.",
        "price": 22.00,
        "image_url": "/static/images/acai.jpg",
    },
    {
        "name": "Açaí Power 700ml",
        "category": "Açaí",
        "description": "Porção generosa com morango, paçoca, leite em pó e mel.",
        "price": 29.00,
        "image_url": "/static/images/acai.jpg",
    },
    {
        "name": "Salada de Frutas Frescas",
        "category": "Saudáveis",
        "description": "Seleção diária de frutas da estação (manga, morango, uva, kiwi e banana) com mel.",
        "price": 15.00,
        "image_url": "/static/images/salada.jpg",
    },
    {
        "name": "Combo Express (Pizza + Açaí)",
        "category": "Combos",
        "description": "1 Pizza Artesanal Margherita + 1 Açaí na Tigela 500ml com desconto especial.",
        "price": 62.00,
        "image_url": "/static/images/combo_pizza_acai.jpg",
    },
]


def seed_database(db: Session, include_sample_orders: bool = True) -> None:
    if db.query(Product).count() == 0:
        for item in INITIAL_PRODUCTS:
            db.add(Product(**item))
        db.commit()
    else:
        # Keep image URLs synced for seeded products when assets are updated
        image_map = {item["name"]: item["image_url"] for item in INITIAL_PRODUCTS}
        updated = False
        for prod in db.query(Product).all():
            new_url = image_map.get(prod.name)
            if new_url and prod.image_url != new_url:
                prod.image_url = new_url
                updated = True
        if updated:
            db.commit()

    if include_sample_orders and db.query(Order).count() == 0:
        products = {p.name: p for p in db.query(Product).all()}
        samples = [
            {
                "customer_name": "Mariana Silva",
                "customer_phone": "(79) 99911-2233",
                "delivery_address": "Av. Ministro Geraldo Barreto Sobral, 215 — Jardins, Aracaju",
                "payment_method": "Pix",
                "channel": "ai_chat",
                "status": "entregue",
                "items": [("Pizza Artesanal Margherita", 1), ("Açaí na Tigela 500ml", 2)],
            },
            {
                "customer_name": "Carlos Eduardo",
                "customer_phone": "(79) 98844-5566",
                "delivery_address": "Rua Urquiza Leal, 410 — Salgado Filho, Aracaju",
                "payment_method": "Cartão de Crédito",
                "channel": "web",
                "status": "em_preparo",
                "items": [("Combo Express (Pizza + Açaí)", 1), ("Salada de Frutas Frescas", 1)],
            },
            {
                "customer_name": "Fernanda Costa",
                "customer_phone": "(79) 99123-7788",
                "delivery_address": "Av. Beira Mar, 980 — 13 de Julho, Aracaju",
                "payment_method": "Pix",
                "channel": "ai_chat",
                "status": "recebido",
                "items": [("Pizza Calabresa Especial", 2)],
            },
        ]
        for s in samples:
            order = Order(
                customer_name=s["customer_name"],
                customer_phone=s["customer_phone"],
                delivery_address=s["delivery_address"],
                payment_method=s["payment_method"],
                channel=s["channel"],
                status=s["status"],
                total_amount=0.0,
            )
            total = 0.0
            for pname, qty in s["items"]:
                prod = products[pname]
                sub = round(prod.price * qty, 2)
                total += sub
                order.items.append(
                    OrderItem(
                        product_id=prod.id,
                        product_name=prod.name,
                        unit_price=prod.price,
                        quantity=qty,
                        subtotal=sub,
                    )
                )
            order.total_amount = round(total, 2)
            db.add(order)
        db.commit()

def test_health_and_menu_seeded(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    menu = client.get("/api/menu")
    assert menu.status_code == 200
    products = menu.json()
    assert len(products) >= 6
    assert any("Pizza" in p["name"] for p in products)


def test_create_order_calculates_total_server_side_and_logs_telegram(client):
    products = client.get("/api/menu").json()
    pizza = next(p for p in products if "Margherita" in p["name"])
    acai = next(p for p in products if "500ml" in p["name"])

    resp = client.post(
        "/api/orders",
        json={
            "customer_name": "Jonas Santos",
            "delivery_address": "Av. Beira Mar, 500 - Aracaju",
            "payment_method": "Pix",
            "channel": "web",
            "items": [
                {"product_id": pizza["id"], "quantity": 1},
                {"product_id": pizza["id"], "quantity": 1},  # duplicate product consolidated
                {"product_id": acai["id"], "quantity": 2},
            ],
        },
    )
    assert resp.status_code == 201
    order = resp.json()
    expected_total = round(pizza["price"] * 2 + acai["price"] * 2, 2)
    assert order["total_amount"] == expected_total
    assert len(order["items"]) == 2
    assert len(order["notifications"]) == 1
    assert order["notifications"][0]["channel"] == "telegram"
    assert order["notifications"][0]["mode"] == "simulated"


def test_order_status_state_machine_and_invalid_transition(client):
    products = client.get("/api/menu").json()
    order = client.post(
        "/api/orders",
        json={
            "customer_name": "Maria",
            "delivery_address": "Rua A, 123 - Jardins",
            "items": [{"product_id": products[0]["id"], "quantity": 1}],
        },
    ).json()

    r1 = client.patch(f"/api/orders/{order['id']}/status", json={"status": "em_preparo"})
    assert r1.status_code == 200
    assert r1.json()["status"] == "em_preparo"

    # Cannot jump directly from em_preparo to entregue
    r_bad = client.patch(f"/api/orders/{order['id']}/status", json={"status": "entregue"})
    assert r_bad.status_code == 400


def test_ai_assistant_parses_natural_language_and_auto_creates_order(client):
    resp = client.post(
        "/api/assistant/parse",
        json={
            "message": "Sou Jonas, quero 1 Pizza Calabresa e duas saladas de frutas na Av. Beira Mar, 500, pago no Pix",
            "auto_create": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready_to_confirm"] is True
    assert data["customer_name"] == "Jonas"
    assert "Beira Mar" in data["delivery_address"]
    assert data["payment_method"] == "Pix"
    assert len(data["items"]) == 2
    # Pizza Calabresa (48) + 2x Salada (15) = 78.00
    assert data["estimated_total"] == 78.00
    assert data["created_order"] is not None
    assert data["created_order"]["channel"] == "ai_chat"


def test_ai_assistant_detects_missing_fields(client):
    resp = client.post(
        "/api/assistant/parse",
        json={
            "message": "Quero 1 Combo Express no cartão de crédito",
            "auto_create": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready_to_confirm"] is False
    assert "nome do cliente" in data["missing_fields"]
    assert "endereço de entrega" in data["missing_fields"]
    assert data["estimated_total"] == 62.00


def test_analytics_summary_and_pandas_csv_export(client):
    products = client.get("/api/menu").json()
    p0 = products[0]

    o1 = client.post(
        "/api/orders",
        json={
            "customer_name": "Cliente 1",
            "delivery_address": "Rua Um, 100",
            "payment_method": "Pix",
            "channel": "ai_chat",
            "items": [{"product_id": p0["id"], "quantity": 2}],
        },
    ).json()

    o2 = client.post(
        "/api/orders",
        json={
            "customer_name": "Cliente Cancelado",
            "delivery_address": "Rua Dois, 200",
            "payment_method": "Dinheiro",
            "channel": "web",
            "items": [{"product_id": p0["id"], "quantity": 1}],
        },
    ).json()
    client.patch(f"/api/orders/{o2['id']}/status", json={"status": "cancelado"})

    summary = client.get("/api/analytics/summary").json()
    assert summary["total_orders"] == 2
    assert summary["valid_orders"] == 1
    assert summary["canceled_orders"] == 1
    assert summary["total_revenue"] == round(p0["price"] * 2, 2)
    assert summary["average_ticket"] == o1["total_amount"]
    assert summary["top_products"][0]["quantity_sold"] == 2

    csv_resp = client.get("/api/analytics/export.csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    text = csv_resp.content.decode("utf-8-sig")
    assert "pedido_id;data_utc;cliente" in text
    assert "Cliente 1" in text

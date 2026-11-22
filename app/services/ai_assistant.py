import json
import re
import unicodedata
from typing import Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Product
from app.schemas import AssistantResponse, OrderCreate, OrderItemIn, ParsedItem, PaymentMethod
from app.services.order_service import create_order


class LLMExtractedItem(BaseModel):
    product_id: int = Field(..., description="ID exato de um produto presente no cardápio fornecido")
    quantity: int = Field(..., ge=1, le=50)


class LLMOrderExtraction(BaseModel):
    items: list[LLMExtractedItem] = []
    customer_name: Optional[str] = None
    delivery_address: Optional[str] = None
    payment_method: Literal["Pix", "Cartão de Crédito", "Cartão de Débito", "Dinheiro"] = "Pix"
    notes: Optional[str] = None
    reply: str = Field(..., description="Resposta cordial e objetiva em português confirmando o que foi entendido")


NUMBER_WORDS = {
    "um": 1, "uma": 1,
    "dois": 2, "duas": 2,
    "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8,
    "nove": 9, "dez": 10,
}

# Ordered from most specific to most general to avoid double-matching
ITEM_PATTERNS: list[tuple[str, str]] = [
    (r"combos?(?:\s+express)?", "Combo Express (Pizza + Açaí)"),
    (r"pizzas?\s+(?:de\s+)?calabresa(?:\s+especial)?", "Pizza Calabresa Especial"),
    (r"pizzas?(?:\s+(?:artesanais|artesanal|margherita|mussarela|de\s+queijo))?", "Pizza Artesanal Margherita"),
    (r"acais?\s+(?:power|700\s*ml|grande)", "Açaí Power 700ml"),
    (r"acais?(?:\s+(?:na\s+tigela|500\s*ml|medio))?", "Açaí na Tigela 500ml"),
    (r"saladas?(?:\s+de\s+frutas?(?:\s+frescas)?)?", "Salada de Frutas Frescas"),
]


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower()


def _parse_offline_demo(message: str, products: list[Product]) -> LLMOrderExtraction:
    norm = _normalize(message)
    by_name = {p.name: p for p in products}

    # 1. Extract items + quantities while masking matched spans so "pizza calabresa" isn't re-matched as "pizza"
    extracted: dict[int, int] = {}
    working = norm
    qty_token = r"(?:(\d+|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez)\s+)?"

    for pattern, canonical_name in ITEM_PATTERNS:
        prod = by_name.get(canonical_name)
        if not prod:
            continue
        regex = re.compile(rf"\b{qty_token}({pattern}s?)\b")
        for match in list(regex.finditer(working)):
            raw_qty = match.group(1)
            if raw_qty is None:
                qty = 1
            elif raw_qty.isdigit():
                qty = min(int(raw_qty), 50)
            else:
                qty = NUMBER_WORDS.get(raw_qty, 1)
            extracted[prod.id] = extracted.get(prod.id, 0) + max(qty, 1)
            start, end = match.span()
            working = working[:start] + (" " * (end - start)) + working[end:]

    # 2. Extract payment method
    payment: PaymentMethod = "Pix"
    if re.search(r"\b(credito|cartao de credito|cartao)\b", norm):
        payment = "Cartão de Crédito"
    elif re.search(r"\b(debito|cartao de debito)\b", norm):
        payment = "Cartão de Débito"
    elif re.search(r"\b(dinheiro|especie|troco)\b", norm):
        payment = "Dinheiro"
    elif re.search(r"\bpix\b", norm):
        payment = "Pix"

    # 3. Extract customer name
    customer_name = None
    name_match = re.search(
        r"(?i:\b(?:meu nome [eé]|sou o|sou a|sou|para|cliente:?))\s+([A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+){0,2})",
        message,
    )
    if name_match:
        candidate = name_match.group(1).strip()
        if _normalize(candidate) not in {"entregar", "entrega", "pix", "dinheiro", "cartao", "rua", "avenida"}:
            customer_name = candidate

    # 4. Extract delivery address
    delivery_address = None
    addr_patterns = [
        r"(?:endere[cç]o:?|entregar?\s+(?:na|no|em)|entrega\s+(?:na|no|em)|para\s+(?:a\s+)?(?:rua|av\.?|avenida))\s+([^;!\n]+?)(?=(?:\s*,?\s*(?:pag(?:o|amento|ando)?|no pix|em dinheiro|no cart|obs|sou |meu nome|$)))",
        r"\b((?:Rua|Av\.?|Avenida|Travessa|Alameda)\s+[^;!\n]+?)(?=(?:\s*,?\s*(?:pag(?:o|amento|ando)?|no pix|em dinheiro|no cart|obs|sou |meu nome|$)))",
    ]
    for ap in addr_patterns:
        m = re.search(ap, message, flags=re.IGNORECASE)
        if m:
            delivery_address = m.group(1).strip(" ,.-")
            if len(delivery_address) >= 5:
                break
            delivery_address = None

    items = [LLMExtractedItem(product_id=pid, quantity=qty) for pid, qty in extracted.items()]
    if not items:
        reply = (
            "Não identifiquei itens do cardápio na sua mensagem. "
            "Você pode pedir, por exemplo: 'Sou Jonas, quero 1 Pizza Calabresa e 2 Açaís na Av. Beira Mar, 500, pago no Pix'."
        )
    else:
        reply = "Entendi seu pedido! Conferi os itens diretamente no cardápio oficial da Delicious Express."

    return LLMOrderExtraction(
        items=items,
        customer_name=customer_name,
        delivery_address=delivery_address,
        payment_method=payment,
        notes=None,
        reply=reply,
    )


def _parse_with_gemini(message: str, products: list[Product]) -> LLMOrderExtraction:
    from google import genai
    from google.genai import types

    catalog_text = "\n".join(
        f"- ID {p.id}: {p.name} ({p.category}) — R$ {p.price:.2f} | {p.description}"
        for p in products
    )
    prompt = (
        "Você é o assistente virtual da lanchonete Delicious Express (Aracaju/SE).\n"
        "Interprete o pedido do cliente em linguagem natural e extraia os dados estruturados.\n"
        "REGRAS ESTRITAS:\n"
        "1. Use SOMENTE product_id presentes no cardápio abaixo. NUNCA invente produtos ou preços.\n"
        "2. Se o cliente mencionar apenas 'pizza', escolha Pizza Artesanal Margherita; se 'açaí', escolha Açaí na Tigela 500ml.\n"
        "3. Só preencha customer_name e delivery_address se estiverem explicitamente na mensagem.\n"
        "4. Responda em português de forma amigável e breve no campo reply.\n\n"
        f"CARDÁPIO ATUAL:\n{catalog_text}\n\n"
        f"MENSAGEM DO CLIENTE:\n{message}"
    )

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMOrderExtraction,
            temperature=0.1,
        ),
    )
    raw = response.text
    return LLMOrderExtraction.model_validate(json.loads(raw))


async def process_assistant_message(
    db: Session,
    message: str,
    auto_create: bool = False,
) -> AssistantResponse:
    products = db.query(Product).filter(Product.available.is_(True)).all()
    product_map = {p.id: p for p in products}

    engine: Literal["gemini", "demo_offline"] = "demo_offline"
    extraction: LLMOrderExtraction

    if settings.ai_enabled:
        try:
            extraction = _parse_with_gemini(message, products)
            engine = "gemini"
        except Exception:
            # Graceful fallback so the app never breaks if quota/network fails
            extraction = _parse_offline_demo(message, products)
            engine = "demo_offline"
    else:
        extraction = _parse_offline_demo(message, products)

    # Deterministic guardrail: validate IDs and calculate exact prices server-side
    validated_items: list[ParsedItem] = []
    merged_qty: dict[int, int] = {}
    for item in extraction.items:
        if item.product_id in product_map:
            merged_qty[item.product_id] = merged_qty.get(item.product_id, 0) + item.quantity

    total = 0.0
    for pid, qty in merged_qty.items():
        prod = product_map[pid]
        sub = round(prod.price * qty, 2)
        total += sub
        validated_items.append(
            ParsedItem(
                product_id=prod.id,
                product_name=prod.name,
                quantity=qty,
                unit_price=prod.price,
                subtotal=sub,
            )
        )
    total = round(total, 2)

    missing_fields: list[str] = []
    if not validated_items:
        missing_fields.append("itens do cardápio")
    if not extraction.customer_name:
        missing_fields.append("nome do cliente")
    if not extraction.delivery_address:
        missing_fields.append("endereço de entrega")

    ready = len(missing_fields) == 0
    reply = extraction.reply
    if not ready and validated_items:
        reply += f" Para finalizar o pedido, informe: {', '.join(missing_fields)}."

    created_order = None
    if auto_create and ready:
        created_order = await create_order(
            db,
            OrderCreate(
                customer_name=extraction.customer_name,
                delivery_address=extraction.delivery_address,
                payment_method=extraction.payment_method,
                notes=extraction.notes,
                channel="ai_chat",
                items=[OrderItemIn(product_id=i.product_id, quantity=i.quantity) for i in validated_items],
            ),
        )
        reply = f"Pedido #{created_order.id} confirmado com sucesso! Total: R$ {created_order.total_amount:.2f}."

    return AssistantResponse(
        engine=engine,
        reply=reply,
        ready_to_confirm=ready,
        missing_fields=missing_fields,
        customer_name=extraction.customer_name,
        delivery_address=extraction.delivery_address,
        payment_method=extraction.payment_method,
        notes=extraction.notes,
        items=validated_items,
        estimated_total=total,
        created_order=created_order,
    )

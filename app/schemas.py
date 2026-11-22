from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


OrderStatus = Literal["recebido", "em_preparo", "saiu_para_entrega", "entregue", "cancelado"]
PaymentMethod = Literal["Pix", "Cartão de Crédito", "Cartão de Débito", "Dinheiro"]
OrderChannel = Literal["web", "ai_chat"]


# --- Products ---
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    category: str = Field(..., min_length=2, max_length=60)
    description: str = Field(..., min_length=5)
    price: float = Field(..., gt=0)
    image_url: Optional[str] = None
    available: bool = True


class ProductOut(ProductCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


# --- Orders ---
class OrderItemIn(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., ge=1, le=50)


class OrderItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    unit_price: float
    quantity: int
    subtotal: float
    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=120)
    customer_phone: Optional[str] = Field(default=None, max_length=40)
    delivery_address: str = Field(..., min_length=5, max_length=255)
    payment_method: PaymentMethod = "Pix"
    notes: Optional[str] = Field(default=None, max_length=500)
    channel: OrderChannel = "web"
    items: list[OrderItemIn] = Field(..., min_length=1)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class NotificationLogOut(BaseModel):
    id: int
    order_id: int
    channel: str
    mode: str
    message: str
    status_detail: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OrderOut(BaseModel):
    id: int
    customer_name: str
    customer_phone: Optional[str]
    delivery_address: str
    payment_method: str
    notes: Optional[str]
    channel: str
    status: str
    total_amount: float
    created_at: datetime
    items: list[OrderItemOut]
    notifications: list[NotificationLogOut] = []
    model_config = ConfigDict(from_attributes=True)


# --- AI Assistant ---
class AssistantRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=1000)
    auto_create: bool = False


class ParsedItem(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    subtotal: float


class AssistantResponse(BaseModel):
    engine: Literal["gemini", "demo_offline"]
    reply: str
    ready_to_confirm: bool
    missing_fields: list[str]
    customer_name: Optional[str] = None
    delivery_address: Optional[str] = None
    payment_method: PaymentMethod = "Pix"
    notes: Optional[str] = None
    items: list[ParsedItem] = []
    estimated_total: float = 0.0
    created_order: Optional[OrderOut] = None


# --- Analytics ---
class TopProductStat(BaseModel):
    product_name: str
    quantity_sold: int
    revenue: float


class AnalyticsSummary(BaseModel):
    total_orders: int
    valid_orders: int
    canceled_orders: int
    total_revenue: float
    average_ticket: float
    orders_by_status: dict[str, int]
    orders_by_channel: dict[str, int]
    orders_by_payment: dict[str, int]
    top_products: list[TopProductStat]

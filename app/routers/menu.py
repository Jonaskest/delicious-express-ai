from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product
from app.schemas import ProductCreate, ProductOut

router = APIRouter(prefix="/api/menu", tags=["Cardápio"])


@router.get("", response_model=list[ProductOut])
def get_menu(category: str | None = None, only_available: bool = True, db: Session = Depends(get_db)):
    query = db.query(Product)
    if only_available:
        query = query.filter(Product.available.is_(True))
    if category:
        query = query.filter(Product.category == category)
    return query.order_by(Product.id.asc()).all()


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def add_product(payload: ProductCreate, db: Session = Depends(get_db)):
    if db.query(Product).filter(Product.name == payload.name).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um produto cadastrado com este nome.",
        )
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

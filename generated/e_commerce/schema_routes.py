from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db import get_db
from models import Product, Customer, Order, Payment, Billing
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix='/api/tdm')

# Pydantic create models
class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    price: float

class CustomerCreate(BaseModel):
    first_name: str
    last_name: str
    email: str

class OrderCreate(BaseModel):
    customer_id: int
    product_id: int
    quantity: int

class PaymentCreate(BaseModel):
    order_id: int
    amount: float
    method: str

class BillingCreate(BaseModel):
    order_id: int
    amount: float
    due_date: str
    paid: bool = False

# GET endpoints
async def get_products(limit: int = Query(None, ge=1), db: Session = Depends(get_db)):
    query = db.query(Product)
    if limit:
        query = query.limit(limit)
    return query.all()

async def get_customers(limit: int = Query(None, ge=1), db: Session = Depends(get_db)):
    query = db.query(Customer)
    if limit:
        query = query.limit(limit)
    return query.all()

async def get_orders(limit: int = Query(None, ge=1), db: Session = Depends(get_db)):
    query = db.query(Order)
    if limit:
        query = query.limit(limit)
    return query.all()

async def get_payments(limit: int = Query(None, ge=1), db: Session = Depends(get_db)):
    query = db.query(Payment)
    if limit:
        query = query.limit(limit)
    return query.all()

async def get_billings(limit: int = Query(None, ge=1), db: Session = Depends(get_db)):
    query = db.query(Billing)
    if limit:
        query = query.limit(limit)
    return query.all()

# POST endpoints
async def create_product(product_in: ProductCreate, db: Session = Depends(get_db)):
    new_product = Product(**product_in.dict())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

async def create_customer(customer_in: CustomerCreate, db: Session = Depends(get_db)):
    new_customer = Customer(**customer_in.dict())
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    return new_customer

async def create_order(order_in: OrderCreate, db: Session = Depends(get_db)):
    new_order = Order(**order_in.dict())
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order

async def create_payment(payment_in: PaymentCreate, db: Session = Depends(get_db)):
    new_payment = Payment(**payment_in.dict())
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    return new_payment

async def create_billing(billing_in: BillingCreate, db: Session = Depends(get_db)):
    new_billing = Billing(**billing_in.dict())
    db.add(new_billing)
    db.commit()
    db.refresh(new_billing)
    return new_billing

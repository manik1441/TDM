from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db import get_db
from models import Customers, Products, Orders, OrderItems, Categories

router = APIRouter(prefix='/api/tdm')

@router.get('/customers')
def get_customers(limit: int = Query(default=10, ge=1), db: Session = Depends(get_db)):
    return db.query(Customers).limit(limit).all()

@router.post('/customers')
def create_customer(customer: dict, db: Session = Depends(get_db)):
    db_customer = Customers(**customer)
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

@router.get('/products')
def get_products(limit: int = Query(default=10, ge=1), db: Session = Depends(get_db)):
    return db.query(Products).limit(limit).all()

@router.post('/products')
def create_product(product: dict, db: Session = Depends(get_db)):
    db_product = Products(**product)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@router.get('/orders')
def get_orders(limit: int = Query(default=10, ge=1), db: Session = Depends(get_db)):
    return db.query(Orders).limit(limit).all()

@router.post('/orders')
def create_order(order: dict, db: Session = Depends(get_db)):
    db_order = Orders(**order)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

@router.get('/order_items')
def get_order_items(limit: int = Query(default=10, ge=1), db: Session = Depends(get_db)):
    return db.query(OrderItems).limit(limit).all()

@router.post('/order_items')
def create_order_item(order_item: dict, db: Session = Depends(get_db)):
    db_order_item = OrderItems(**order_item)
    db.add(db_order_item)
    db.commit()
    db.refresh(db_order_item)
    return db_order_item

@router.get('/categories')
def get_categories(limit: int = Query(default=10, ge=1), db: Session = Depends(get_db)):
    return db.query(Categories).limit(limit).all()

@router.post('/categories')
def create_category(category: dict, db: Session = Depends(get_db)):
    db_category = Categories(**category)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category
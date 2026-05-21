from sqlalchemy import Column, String, Integer, Float, ForeignKey, Text, Date, Boolean
from sqlalchemy.orm import relationship
from app.db import Base

class Customers(Base):
    __tablename__ = 'customers'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    address = Column(Text)
    registration_date = Column(Date)

    orders = relationship('Orders', back_populates='customer')

class Products(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    stock_quantity = Column(Integer, default=0)

    category = relationship('Categories', back_populates='products')
    order_items = relationship('OrderItems', back_populates='product')

class Categories(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    products = relationship('Products', back_populates='category')

class Orders(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    order_date = Column(Date, nullable=False)
    total_amount = Column(Float, default=0.0)
    status = Column(String(50), default='Pending')

    customer = relationship('Customers', back_populates='orders')
    order_items = relationship('OrderItems', back_populates='order')

class OrderItems(Base):
    __tablename__ = 'order_items'

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)

    order = relationship('Orders', back_populates='order_items')
    product = relationship('Products', back_populates='order_items')
from app.db import Base
from sqlalchemy import Column, String, Integer, Float, Date, Boolean, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

class Product(Base):
    __tablename__ = 'product'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    def __repr__(self):
        return f'<Product(id={self.id}, name={self.name!r}, price={self.price})>'

class Customer(Base):
    __tablename__ = 'customer'
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    def __repr__(self):
        return f'<Customer(id={self.id}, first_name={self.first_name!r}, last_name={self.last_name!r}, email={self.email!r})>'
    orders = relationship('Order', back_populates='customer', cascade='all, delete-orphan')

class Order(Base):
    __tablename__ = 'order'
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey('customer.id'), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('product.id'), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    order_date = Column(Date, nullable=False, index=True)
    customer = relationship('Customer', back_populates='orders')
    def __repr__(self):
        return f'<Order(id={self.id}, customer_id={self.customer_id}, product_id={self.product_id}, quantity={self.quantity}, order_date={self.order_date})>'

class Payment(Base):
    __tablename__ = 'payment'
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('order.id'), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    method = Column(String(20), nullable=False)
    payment_date = Column(Date, nullable=False, index=True)
    def __repr__(self):
        return f'<Payment(id={self.id}, order_id={self.order_id}, amount={self.amount}, method={self.method!r}, payment_date={self.payment_date})>'

class Billing(Base):
    __tablename__ = 'billing'
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('order.id'), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    due_date = Column(Date, nullable=False, index=True)
    paid = Column(Boolean, nullable=False, default=False)
    def __repr__(self):
        return f'<Billing(id={self.id}, order_id={self.order_id}, amount={self.amount}, due_date={self.due_date}, paid={self.paid})>'

# These models are intended for synthetic test data (~100 rows, scale_factor=0.01)

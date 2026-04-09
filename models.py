from sqlalchemy import Column, String, Integer, Float, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from database import Base

class Office(Base):
    __tablename__ = "offices"
    officeCode = Column(String(10), primary_key=True, index=True)
    city = Column(String(50))
    phone = Column(String(50))
    addressLine1 = Column(String(50))
    addressLine2 = Column(String(50), nullable=True)
    state = Column(String(50), nullable=True)
    country = Column(String(50))
    postalCode = Column(String(15))
    territory = Column(String(10))

class Employee(Base):
    __tablename__ = "employees"
    employeeNumber = Column(Integer, primary_key=True, index=True)
    lastName = Column(String(50))
    firstName = Column(String(50))
    extension = Column(String(10))
    email = Column(String(100))
    officeCode = Column(String(10), ForeignKey("offices.officeCode"))
    reportsTo = Column(Integer, ForeignKey("employees.employeeNumber"), nullable=True)
    jobTitle = Column(String(50))
    # Note: In SQLite foreign key enforcement is off by default, making invalid data injection easy for POC

class ProductLine(Base):
    __tablename__ = "productlines"
    productLine = Column(String(50), primary_key=True, index=True)
    textDescription = Column(String(4000), nullable=True)
    htmlDescription = Column(Text, nullable=True)
    image = Column(String(255), nullable=True) # Treating mediumblob as string URL for POC purposes

class Product(Base):
    __tablename__ = "products"
    productCode = Column(String(15), primary_key=True, index=True)
    productName = Column(String(70))
    productLine = Column(String(50), ForeignKey("productlines.productLine"))
    productScale = Column(String(10))
    productVendor = Column(String(50))
    productDescription = Column(Text)
    quantityInStock = Column(Integer)
    buyPrice = Column(Float)
    MSRP = Column(Float)

class Customer(Base):
    __tablename__ = "customers"
    customerNumber = Column(Integer, primary_key=True, index=True)
    customerName = Column(String(50))
    contactLastName = Column(String(50))
    contactFirstName = Column(String(50))
    phone = Column(String(50))
    addressLine1 = Column(String(50))
    addressLine2 = Column(String(50), nullable=True)
    city = Column(String(50))
    state = Column(String(50), nullable=True)
    postalCode = Column(String(15), nullable=True)
    country = Column(String(50))
    salesRepEmployeeNumber = Column(Integer, ForeignKey("employees.employeeNumber"), nullable=True)
    creditLimit = Column(Float, nullable=True)

class Order(Base):
    __tablename__ = "orders"
    orderNumber = Column(Integer, primary_key=True, index=True)
    orderDate = Column(Date)
    requiredDate = Column(Date)
    shippedDate = Column(Date, nullable=True)
    status = Column(String(15))
    comments = Column(Text, nullable=True)
    customerNumber = Column(Integer, ForeignKey("customers.customerNumber"))

class OrderDetail(Base):
    __tablename__ = "orderdetails"
    orderNumber = Column(Integer, ForeignKey("orders.orderNumber"), primary_key=True)
    productCode = Column(String(15), ForeignKey("products.productCode"), primary_key=True)
    quantityOrdered = Column(Integer)
    priceEach = Column(Float)
    orderLineNumber = Column(Integer)

class Payment(Base):
    __tablename__ = "payments"
    customerNumber = Column(Integer, ForeignKey("customers.customerNumber"), primary_key=True)
    checkNumber = Column(String(50), primary_key=True)
    paymentDate = Column(Date)
    amount = Column(Float)

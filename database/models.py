from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    username = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    registered_at = Column(DateTime, default=datetime.utcnow)
    is_banned = Column(Boolean, default=False)
    used_promocodes = Column(Text, default="")

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    parent_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    is_active = Column(Boolean, default=True)
    products = relationship("Product", back_populates="category", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('categories.id'))
    name = Column(String)
    price = Column(Float)
    quantity = Column(Integer, default=0)
    content = Column(Text, nullable=True)       # многострочный текст, каждая строка = 1 единица
    file_id = Column(String, nullable=True)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    category = relationship("Category", back_populates="products")

class Purchase(Base):
    __tablename__ = 'purchases'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    price = Column(Float)
    amount = Column(Integer, default=1)
    purchased_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default='completed')

class Promocode(Base):
    __tablename__ = 'promocodes'
    code = Column(String, primary_key=True)
    bonus_amount = Column(Float, default=0.0)
    max_activations = Column(Integer, nullable=True)
    used_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

class ReplaceRequest(Base):
    __tablename__ = 'replace_requests'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    purchase_id = Column(Integer, ForeignKey('purchases.id'))
    phone_number = Column(String)
    date_time = Column(String)
    status = Column(String, default='pending')
    admin_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Invoice(Base):
    __tablename__ = 'invoices'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    invoice_id = Column(Integer)
    amount = Column(Float)
    status = Column(String, default='active')
    created_at = Column(DateTime, default=datetime.utcnow)

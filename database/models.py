from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, BigInteger
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id      = Column(BigInteger, primary_key=True)
    username     = Column(String, nullable=True)
    balance      = Column(Float, default=0.0)
    cashback_pct = Column(Float, default=1.0)          # % кэшбека
    total_spent  = Column(Float, default=0.0)           # всего потрачено
    registered_at= Column(DateTime, default=datetime.utcnow)
    is_banned    = Column(Boolean, default=False)
    ban_reason   = Column(Text, nullable=True)
    used_promocodes = Column(Text, default="")
    ref_code     = Column(String, unique=True, nullable=True)  # реф-код пользователя
    referred_by  = Column(BigInteger, ForeignKey('users.user_id'), nullable=True)
    ref_count    = Column(Integer, default=0)           # сколько привёл

class Category(Base):
    __tablename__ = 'categories'
    id        = Column(Integer, primary_key=True)
    name      = Column(String)
    parent_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    is_active = Column(Boolean, default=True)
    products  = relationship("Product", back_populates="category", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = 'products'
    id           = Column(Integer, primary_key=True)
    category_id  = Column(Integer, ForeignKey('categories.id'))
    name         = Column(String)
    description  = Column(Text, nullable=True)
    price        = Column(Float)
    quantity     = Column(Integer, default=0)
    content      = Column(Text, nullable=True)
    file_id      = Column(String, nullable=True)
    is_available = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    # рейтинг
    rating_sum   = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    category     = relationship("Category", back_populates="products")

class Purchase(Base):
    __tablename__ = 'purchases'
    id           = Column(Integer, primary_key=True)
    user_id      = Column(BigInteger, ForeignKey('users.user_id'))
    product_id   = Column(Integer, ForeignKey('products.id'))
    price        = Column(Float)
    amount       = Column(Integer, default=1)
    cashback     = Column(Float, default=0.0)   # начислен кэшбек
    purchased_at = Column(DateTime, default=datetime.utcnow)
    status       = Column(String, default='completed')

class Review(Base):
    __tablename__ = 'reviews'
    id         = Column(Integer, primary_key=True)
    user_id    = Column(BigInteger, ForeignKey('users.user_id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    purchase_id= Column(Integer, ForeignKey('purchases.id'))
    rating     = Column(Integer)   # 1-5
    text       = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Promocode(Base):
    __tablename__ = 'promocodes'
    code            = Column(String, primary_key=True)
    bonus_amount    = Column(Float, default=0.0)
    max_activations = Column(Integer, nullable=True)
    used_count      = Column(Integer, default=0)
    expires_at      = Column(DateTime, nullable=True)
    is_active       = Column(Boolean, default=True)

class ReplaceRequest(Base):
    __tablename__ = 'replace_requests'
    id            = Column(Integer, primary_key=True)
    user_id       = Column(BigInteger, ForeignKey('users.user_id'))
    purchase_id   = Column(Integer, ForeignKey('purchases.id'))
    log_info      = Column(String)
    photos        = Column(Text)
    complaint     = Column(Text)
    status        = Column(String, default='pending')
    admin_comment = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

class Invoice(Base):
    __tablename__ = 'invoices'
    id         = Column(Integer, primary_key=True)
    user_id    = Column(BigInteger, ForeignKey('users.user_id'))
    invoice_id = Column(BigInteger)
    amount     = Column(Float)
    asset      = Column(String, default='USDT')
    status     = Column(String, default='active')
    created_at = Column(DateTime, default=datetime.utcnow)

class UnbanRequest(Base):
    __tablename__ = 'unban_requests'
    id          = Column(Integer, primary_key=True)
    user_id     = Column(BigInteger, ForeignKey('users.user_id'))
    photos      = Column(Text)
    description = Column(Text)
    status      = Column(String, default='pending')
    created_at  = Column(DateTime, default=datetime.utcnow)

class UserDiscount(Base):
    __tablename__ = 'user_discounts'
    id         = Column(Integer, primary_key=True)
    user_id    = Column(BigInteger, ForeignKey('users.user_id'), unique=True)
    percent    = Column(Integer)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class StockNotify(Base):
    """Уведомить когда товар появится"""
    __tablename__ = 'stock_notify'
    id         = Column(Integer, primary_key=True)
    user_id    = Column(BigInteger, ForeignKey('users.user_id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    created_at = Column(DateTime, default=datetime.utcnow)

class ScheduledBroadcast(Base):
    __tablename__ = 'scheduled_broadcasts'
    id         = Column(Integer, primary_key=True)
    text       = Column(Text)
    send_at    = Column(DateTime)
    sent       = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

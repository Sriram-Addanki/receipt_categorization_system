"""
Database models and configuration
SQLAlchemy ORM models for receipt categorization system
"""
from sqlalchemy import create_engine, Column, Integer, String, Numeric, Boolean, DateTime, Date, JSON, ARRAY, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
import os

Base = declarative_base()

# ============================================
# Models
# ============================================

class IRSCategory(Base):
    __tablename__ = 'irs_categories'
    
    id = Column(Integer, primary_key=True)
    category_name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    parent_category = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'category_name': self.category_name,
            'description': self.description,
            'parent_category': self.parent_category,
            'is_active': self.is_active
        }


class MerchantCategory(Base):
    __tablename__ = 'merchant_categories'
    
    id = Column(Integer, primary_key=True)
    merchant_name = Column(String(255), nullable=False)
    merchant_name_normalized = Column(String(255), nullable=False, unique=True)
    category_name = Column(String(100), ForeignKey('irs_categories.category_name'), nullable=False)
    confidence_score = Column(Numeric(5, 4), default=0.0)
    total_confirmations = Column(Integer, default=0)
    total_corrections = Column(Integer, default=0)
    avg_amount = Column(Numeric(10, 2))
    keywords = Column(ARRAY(Text))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'merchant_name': self.merchant_name,
            'merchant_name_normalized': self.merchant_name_normalized,
            'category_name': self.category_name,
            'confidence_score': float(self.confidence_score),
            'total_confirmations': self.total_confirmations,
            'total_corrections': self.total_corrections,
            'total_predictions': self.total_confirmations + self.total_corrections,
            'avg_amount': float(self.avg_amount) if self.avg_amount else None,
            'keywords': self.keywords
        }


class Receipt(Base):
    __tablename__ = 'receipts'
    
    id = Column(Integer, primary_key=True)
    receipt_id = Column(String(50), unique=True, nullable=False)
    user_id = Column(String(50), nullable=False)
    merchant_name = Column(String(255), nullable=False)
    merchant_address = Column(Text)
    total_amount = Column(Numeric(10, 2), nullable=False)
    tax_amount = Column(Numeric(10, 2))
    subtotal = Column(Numeric(10, 2))
    transaction_date = Column(Date, nullable=False)
    payment_method = Column(String(50))
    receipt_data = Column(JSON)  # Full OCR data
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    prediction = relationship("CategorizationPrediction", back_populates="receipt", uselist=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'receipt_id': self.receipt_id,
            'user_id': self.user_id,
            'merchant_name': self.merchant_name,
            'merchant_address': self.merchant_address,
            'total_amount': float(self.total_amount),
            'tax_amount': float(self.tax_amount) if self.tax_amount else None,
            'subtotal': float(self.subtotal) if self.subtotal else None,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'payment_method': self.payment_method,
            'receipt_data': self.receipt_data,
            'created_at': self.created_at.isoformat()
        }


class CategorizationPrediction(Base):
    __tablename__ = 'categorization_predictions'
    
    id = Column(Integer, primary_key=True)
    receipt_id = Column(String(50), ForeignKey('receipts.receipt_id'), nullable=False)
    predicted_category = Column(String(100), ForeignKey('irs_categories.category_name'), nullable=False)
    confidence_score = Column(Numeric(5, 4), nullable=False)
    prediction_method = Column(String(50), nullable=False)
    needs_review = Column(Boolean, default=False)
    confirmed_category = Column(String(100), ForeignKey('irs_categories.category_name'))
    is_confirmed = Column(Boolean, default=False)
    reviewed_by = Column(String(50))
    reviewed_at = Column(DateTime)
    prediction_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    receipt = relationship("Receipt", back_populates="prediction")
    
    def to_dict(self):
        return {
            'id': self.id,
            'receipt_id': self.receipt_id,
            'predicted_category': self.predicted_category,
            'confidence_score': float(self.confidence_score),
            'prediction_method': self.prediction_method,
            'needs_review': self.needs_review,
            'confirmed_category': self.confirmed_category,
            'is_confirmed': self.is_confirmed,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'prediction_reason': self.prediction_reason,
            'created_at': self.created_at.isoformat()
        }


class CategoryKeyword(Base):
    __tablename__ = 'category_keywords'
    
    id = Column(Integer, primary_key=True)
    keyword = Column(String(100), nullable=False)
    category_name = Column(String(100), ForeignKey('irs_categories.category_name'), nullable=False)
    confidence_weight = Column(Numeric(3, 2), default=0.50)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'keyword': self.keyword,
            'category_name': self.category_name,
            'confidence_weight': float(self.confidence_weight),
            'is_active': self.is_active
        }


class FeedbackLog(Base):
    __tablename__ = 'feedback_log'
    
    id = Column(Integer, primary_key=True)
    receipt_id = Column(String(50), nullable=False)
    user_id = Column(String(50), nullable=False)
    predicted_category = Column(String(100))
    confirmed_category = Column(String(100))
    was_correct = Column(Boolean)
    feedback_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'receipt_id': self.receipt_id,
            'user_id': self.user_id,
            'predicted_category': self.predicted_category,
            'confirmed_category': self.confirmed_category,
            'was_correct': self.was_correct,
            'feedback_notes': self.feedback_notes,
            'created_at': self.created_at.isoformat()
        }


# ============================================
# Database Connection
# ============================================

class Database:
    """Database connection manager"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database connection
        
        Args:
            database_url: PostgreSQL connection string
                         Format: postgresql://user:password@localhost:5432/dbname
        """
        if database_url is None:
            # Default connection from environment or use local
            database_url = os.getenv(
                'DATABASE_URL',
                'postgresql://postgres:postgres@localhost:5432/receipt_categorization'
            )
        
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def create_tables(self):
        """Create all tables"""
        Base.metadata.create_all(self.engine)
    
    def get_session(self):
        """Get database session"""
        return self.SessionLocal()
    
    def close(self):
        """Close database connection"""
        self.engine.dispose()


# ============================================
# Helper Functions
# ============================================

def get_db_session():
    """
    Get database session (for dependency injection)
    Use this in FastAPI endpoints
    """
    db = Database()
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()


if __name__ == "__main__":
    # Test database connection
    db = Database()
    print("Database connection successful!")
    print(f"Engine: {db.engine}")
    
    # Create tables
    db.create_tables()
    print("Tables created successfully!")

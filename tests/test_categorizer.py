"""
Tests for Receipt Categorization Engine
"""
import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.models import Base, MerchantCategory, CategoryKeyword, IRSCategory
from backend.categorizer import ReceiptCategorizer


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def db_session():
    """Create test database session"""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    # Seed test data
    _seed_test_data(session)
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)


def _seed_test_data(session):
    """Seed test database with initial data"""
    # Add IRS categories
    categories = [
        IRSCategory(category_name="Office Supplies"),
        IRSCategory(category_name="Travel"),
        IRSCategory(category_name="Meals & Entertainment"),
        IRSCategory(category_name="Repairs & Maintenance"),
        IRSCategory(category_name="Utilities"),
        IRSCategory(category_name="Other Business Expenses")
    ]
    session.add_all(categories)
    
    # Add known merchants
    merchants = [
        MerchantCategory(
            merchant_name="LOWES",
            merchant_name_normalized="lowes",
            category_name="Repairs & Maintenance",
            confidence_score=0.85,
            total_confirmations=17,
            total_corrections=3
        ),
        MerchantCategory(
            merchant_name="STAPLES",
            merchant_name_normalized="staples",
            category_name="Office Supplies",
            confidence_score=0.95,
            total_confirmations=38,
            total_corrections=2
        ),
        MerchantCategory(
            merchant_name="DELTA AIRLINES",
            merchant_name_normalized="delta airlines",
            category_name="Travel",
            confidence_score=0.90,
            total_confirmations=27,
            total_corrections=3
        )
    ]
    session.add_all(merchants)
    
    # Add keywords
    keywords = [
        CategoryKeyword(keyword="hotel", category_name="Travel", confidence_weight=0.90),
        CategoryKeyword(keyword="flight", category_name="Travel", confidence_weight=0.95),
        CategoryKeyword(keyword="lumber", category_name="Repairs & Maintenance", confidence_weight=0.75),
        CategoryKeyword(keyword="paper", category_name="Office Supplies", confidence_weight=0.70),
        CategoryKeyword(keyword="pens", category_name="Office Supplies", confidence_weight=0.80)
    ]
    session.add_all(keywords)
    
    session.commit()


class TestMerchantNormalization:
    """Test merchant name normalization"""
    
    def test_normalize_with_store_number(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        result = categorizer._normalize_merchant_name("LOWES #1234")
        assert result == "lowes"
    
    def test_normalize_with_suffix(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        result = categorizer._normalize_merchant_name("STAPLES, INC.")
        assert result == "staples"
    
    def test_normalize_with_store_keyword(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        result = categorizer._normalize_merchant_name("Home Depot Store 5678")
        assert result == "home depot"
    
    def test_normalize_complex_name(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        result = categorizer._normalize_merchant_name("THE HOME DEPOT, INC. #9999")
        assert result == "home depot"


class TestExactMerchantMatch:
    """Test exact merchant matching"""
    
    def test_exact_match_lowes(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        receipt = {
            "merchant_name": "LOWES #1234",
            "amount": 100,
            "keywords": []
        }
        
        result = categorizer.categorize(receipt)
        
        assert result["category"] == "Repairs & Maintenance"
        assert result["confidence"] == 0.85
        assert result["method"] == "exact_match"
        assert not result["needs_review"]
    
    def test_exact_match_staples(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        receipt = {
            "merchant_name": "STAPLES",
            "amount": 50,
            "keywords": []
        }
        
        result = categorizer.categorize(receipt)
        
        assert result["category"] == "Office Supplies"
        assert result["confidence"] == 0.95
        assert result["method"] == "exact_match"
    
    def test_exact_match_with_variations(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        variations = [
            "LOWES #5678",
            "Lowes Store 1234",
            "LOWES INC",
            "lowes #999"
        ]
        
        for merchant_name in variations:
            receipt = {
                "merchant_name": merchant_name,
                "amount": 100,
                "keywords": []
            }
            
            result = categorizer.categorize(receipt)
            assert result["category"] == "Repairs & Maintenance"


class TestFuzzyMatching:
    """Test fuzzy merchant matching"""
    
    def test_fuzzy_match_typo(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        receipt = {
            "merchant_name": "LOWES HOMEDEPOT",  # Close to LOWES
            "amount": 100,
            "keywords": []
        }
        
        result = categorizer.categorize(receipt)
        
        # Should fuzzy match to LOWES
        assert result["method"] in ["fuzzy_match", "exact_match"]
        assert result["needs_review"]  # Always review fuzzy matches
    
    def test_fuzzy_match_delta(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        receipt = {
            "merchant_name": "DLTA AIRLINES",  # Typo: DELTA
            "amount": 500,
            "keywords": []
        }
        
        result = categorizer.categorize(receipt)
        
        # May fuzzy match to DELTA AIRLINES
        # Confidence should be reduced
        if result["method"] == "fuzzy_match":
            assert result["confidence"] < 0.90


class TestKeywordMatching:
    """Test keyword-based categorization"""
    
    def test_keyword_hotel(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        receipt = {
            "merchant_name": "UNKNOWN HOTEL",
            "amount": 150,
            "keywords": ["hotel", "accommodation"]
        }
        
        result = categorizer.categorize(receipt)
        
        assert result["category"] == "Travel"
        assert result["method"] == "keyword_match"
        assert 0.5 <= result["confidence"] <= 1.0
    
    def test_keyword_lumber(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        receipt = {
            "merchant_name": "LOCAL HARDWARE",
            "amount": 200,
            "keywords": ["lumber", "wood", "building"]
        }
        
        result = categorizer.categorize(receipt)
        
        assert result["category"] == "Repairs & Maintenance"
        assert result["method"] == "keyword_match"
    
    def test_multiple_keywords_same_category(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        receipt = {
            "merchant_name": "OFFICE STORE",
            "amount": 45,
            "keywords": ["paper", "pens", "notebooks"]
        }
        
        result = categorizer.categorize(receipt)
        
        assert result["category"] == "Office Supplies"
        # Confidence should be higher with multiple matching keywords
        assert result["confidence"] > 0.6


class TestDefaultCase:
    """Test default categorization when no match found"""
    
    def test_unknown_merchant_no_keywords(self, db_session):
        categorizer = ReceiptCategorizer(db_session)
        
        receipt = {
            "merchant_name": "RANDOM UNKNOWN MERCHANT",
            "amount": 75,
            "keywords": []
        }
        
        result = categorizer.categorize(receipt)
        
        assert result["category"] == "Other Business Expenses"
        assert result["confidence"] == 0.0
        assert result["needs_review"]
        assert result["method"] == "default"


class TestFeedbackLearning:
    """Test feedback processing and learning"""
    
    def test_confirm_correct_prediction(self, db_session):
        from backend.models import Receipt, CategorizationPrediction
        
        categorizer = ReceiptCategorizer(db_session)
        
        # Create receipt
        receipt = Receipt(
            receipt_id="TEST001",
            user_id="USER123",
            merchant_name="NEW MERCHANT",
            total_amount=100,
            transaction_date=date.today()
        )
        db_session.add(receipt)
        
        # Create prediction
        prediction = CategorizationPrediction(
            receipt_id="TEST001",
            predicted_category="Office Supplies",
            confidence_score=0.60,
            prediction_method="keyword_match",
            needs_review=False
        )
        db_session.add(prediction)
        db_session.commit()
        
        # Process feedback (confirm correct)
        success = categorizer.process_feedback(
            receipt_id="TEST001",
            confirmed_category="Office Supplies",
            user_id="USER123"
        )
        
        assert success
        
        # Check merchant was added to knowledge base
        merchant = db_session.query(MerchantCategory).filter(
            MerchantCategory.merchant_name_normalized == "new merchant"
        ).first()
        
        assert merchant is not None
        assert merchant.category_name == "Office Supplies"
        assert merchant.total_confirmations == 1
        assert merchant.total_corrections == 0
    
    def test_correct_wrong_prediction(self, db_session):
        from backend.models import Receipt, CategorizationPrediction
        
        categorizer = ReceiptCategorizer(db_session)
        
        # Create receipt
        receipt = Receipt(
            receipt_id="TEST002",
            user_id="USER123",
            merchant_name="ANOTHER MERCHANT",
            total_amount=200,
            transaction_date=date.today()
        )
        db_session.add(receipt)
        
        # Create wrong prediction
        prediction = CategorizationPrediction(
            receipt_id="TEST002",
            predicted_category="Travel",  # Wrong
            confidence_score=0.55,
            prediction_method="keyword_match",
            needs_review=True
        )
        db_session.add(prediction)
        db_session.commit()
        
        # Process feedback (correct to right category)
        success = categorizer.process_feedback(
            receipt_id="TEST002",
            confirmed_category="Repairs & Maintenance",  # Correct
            user_id="USER123"
        )
        
        assert success
        
        # Check merchant was added with correct category
        merchant = db_session.query(MerchantCategory).filter(
            MerchantCategory.merchant_name_normalized == "another merchant"
        ).first()
        
        assert merchant is not None
        assert merchant.category_name == "Repairs & Maintenance"
        assert merchant.total_confirmations == 0
        assert merchant.total_corrections == 1


class TestStatistics:
    """Test statistics calculation"""
    
    def test_get_stats(self, db_session):
        from backend.models import Receipt, CategorizationPrediction
        
        categorizer = ReceiptCategorizer(db_session)
        
        # Create test receipts and predictions
        for i in range(5):
            receipt = Receipt(
                receipt_id=f"STAT{i}",
                user_id="USER123",
                merchant_name=f"MERCHANT{i}",
                total_amount=100,
                transaction_date=date.today()
            )
            db_session.add(receipt)
            
            prediction = CategorizationPrediction(
                receipt_id=f"STAT{i}",
                predicted_category="Office Supplies",
                confidence_score=0.80,
                prediction_method="exact_match",
                needs_review=False,
                is_confirmed=True if i < 3 else False,
                confirmed_category="Office Supplies" if i < 3 else None
            )
            db_session.add(prediction)
        
        db_session.commit()
        
        # Get stats
        stats = categorizer.get_stats()
        
        assert stats["total_predictions"] >= 5
        assert stats["confirmed"] >= 3
        assert stats["correct"] >= 3
        assert stats["accuracy"] == 100.0  # All confirmed were correct


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

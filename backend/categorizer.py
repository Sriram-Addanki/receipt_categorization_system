"""
Receipt Categorization Engine
Rule-based categorization with learning capability
"""
import re
from typing import Dict, List, Optional, Tuple
from fuzzywuzzy import fuzz
from sqlalchemy.orm import Session
from models import (
    MerchantCategory, CategoryKeyword, Receipt, 
    CategorizationPrediction, FeedbackLog
)
from datetime import datetime


class ReceiptCategorizer:
    """
    Main categorization engine
    Implements Phase 1: Rule-based categorization with learning
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize categorizer
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.keyword_cache = None
        self.merchant_cache = None
    
    def categorize(self, receipt_data: Dict) -> Dict:
        """
        Main categorization function
        
        Args:
            receipt_data: {
                "receipt_id": "REC001",
                "merchant_name": "LOWES #1234",
                "amount": 145.67,
                "transaction_date": "2026-03-01",
                "keywords": ["lumber", "hardware"],  # Optional
                "description": "Purchase details",    # Optional
                "line_items": [...]                   # Optional
            }
        
        Returns:
            {
                "receipt_id": "REC001",
                "category": "Repairs & Maintenance",
                "confidence": 0.85,
                "needs_review": False,
                "method": "exact_match",
                "reason": "Exact merchant match with high confidence"
            }
        """
        merchant_name = receipt_data.get("merchant_name", "").strip()
        amount = receipt_data.get("amount", 0)
        keywords = receipt_data.get("keywords", [])
        description = receipt_data.get("description", "")
        
        if not merchant_name:
            return self._default_result(receipt_data.get("receipt_id"))
        
        # Strategy 1: Check exact merchant match
        result = self._check_exact_merchant(merchant_name)
        if result and result["confidence"] > 0.7:
            result["receipt_id"] = receipt_data.get("receipt_id")
            return result
        
        # Strategy 2: Check fuzzy merchant match
        result = self._check_fuzzy_merchant(merchant_name)
        if result and result["confidence"] > 0.6:
            result["receipt_id"] = receipt_data.get("receipt_id")
            return result
        
        # Strategy 3: Check keywords
        result = self._check_keywords(keywords, merchant_name, description)
        if result and result["confidence"] > 0.5:
            result["receipt_id"] = receipt_data.get("receipt_id")
            return result
        
        # Strategy 4: Amount-based patterns (weak signal)
        result = self._check_amount_patterns(merchant_name, amount)
        if result and result["confidence"] > 0.4:
            result["receipt_id"] = receipt_data.get("receipt_id")
            return result
        
        # Default: No match found
        return self._default_result(receipt_data.get("receipt_id"))
    
    def _check_exact_merchant(self, merchant_name: str) -> Optional[Dict]:
        """Check for exact merchant match in database"""
        normalized = self._normalize_merchant_name(merchant_name)
        
        merchant = self.db.query(MerchantCategory).filter(
            MerchantCategory.merchant_name_normalized == normalized
        ).first()
        
        if merchant:
            confidence = float(merchant.confidence_score)
            
            return {
                "category": merchant.category_name,
                "confidence": confidence,
                "needs_review": confidence < 0.7,
                "method": "exact_match",
                "reason": f"Exact merchant match (confidence: {confidence:.2%})"
            }
        
        return None
    
    def _check_fuzzy_merchant(self, merchant_name: str) -> Optional[Dict]:
        """Check for similar merchant names using fuzzy matching"""
        normalized = self._normalize_merchant_name(merchant_name)
        
        # Get all merchants from database
        all_merchants = self.db.query(MerchantCategory).all()
        
        best_match = None
        best_score = 0
        
        for merchant in all_merchants:
            # Calculate similarity
            similarity = fuzz.ratio(normalized, merchant.merchant_name_normalized)
            
            if similarity > best_score and similarity > 80:  # 80% threshold
                best_score = similarity
                best_match = merchant
        
        if best_match:
            # Reduce confidence based on similarity
            base_confidence = float(best_match.confidence_score)
            adjusted_confidence = base_confidence * (best_score / 100) * 0.9  # Penalty for fuzzy match
            
            return {
                "category": best_match.category_name,
                "confidence": adjusted_confidence,
                "needs_review": True,  # Always review fuzzy matches
                "method": "fuzzy_match",
                "reason": f"Fuzzy match to '{best_match.merchant_name}' ({best_score}% similar)"
            }
        
        return None
    
    def _check_keywords(self, keywords: List[str], merchant_name: str, description: str) -> Optional[Dict]:
        """Match based on keywords in receipt"""
        
        # Load keyword dictionary
        keyword_dict = self._load_keywords()
        
        matches = []
        
        # Check explicit keywords
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in keyword_dict:
                category, weight = keyword_dict[keyword_lower]
                matches.append({
                    "category": category,
                    "confidence": float(weight),
                    "keyword": keyword
                })
        
        # Check merchant name for keywords
        merchant_lower = merchant_name.lower()
        for keyword, (category, weight) in keyword_dict.items():
            if keyword in merchant_lower:
                matches.append({
                    "category": category,
                    "confidence": float(weight) * 0.9,  # Slight penalty
                    "keyword": keyword
                })
        
        # Check description for keywords
        if description:
            desc_lower = description.lower()
            for keyword, (category, weight) in keyword_dict.items():
                if keyword in desc_lower:
                    matches.append({
                        "category": category,
                        "confidence": float(weight) * 0.8,  # More penalty
                        "keyword": keyword
                    })
        
        if not matches:
            return None
        
        # Aggregate matches by category
        category_scores = {}
        for match in matches:
            cat = match["category"]
            if cat not in category_scores:
                category_scores[cat] = []
            category_scores[cat].append(match["confidence"])
        
        # Get category with highest average confidence
        best_category = max(
            category_scores.items(),
            key=lambda x: sum(x[1]) / len(x[1])
        )
        
        category_name = best_category[0]
        avg_confidence = sum(best_category[1]) / len(best_category[1])
        
        return {
            "category": category_name,
            "confidence": avg_confidence,
            "needs_review": avg_confidence < 0.65,
            "method": "keyword_match",
            "reason": f"Keyword match (found {len(best_category[1])} matching keywords)"
        }
    
    def _check_amount_patterns(self, merchant_name: str, amount: float) -> Optional[Dict]:
        """
        Check amount patterns (weak signal)
        This is a fallback strategy
        """
        # Define typical amount ranges for categories
        # This is a weak signal and should have low confidence
        
        amount_patterns = {
            "Utilities": {"min": 50, "max": 500, "confidence": 0.35},
            "Office Supplies": {"min": 10, "max": 200, "confidence": 0.30},
            "Meals & Entertainment": {"min": 5, "max": 150, "confidence": 0.30},
        }
        
        for category, pattern in amount_patterns.items():
            if pattern["min"] <= amount <= pattern["max"]:
                return {
                    "category": category,
                    "confidence": pattern["confidence"],
                    "needs_review": True,
                    "method": "amount_pattern",
                    "reason": f"Amount matches typical range for {category}"
                }
        
        return None
    
    def _default_result(self, receipt_id: Optional[str] = None) -> Dict:
        """Return default result when no match found"""
        return {
            "receipt_id": receipt_id,
            "category": "Other Business Expenses",
            "confidence": 0.0,
            "needs_review": True,
            "method": "default",
            "reason": "No matching rules found - needs human review"
        }
    
    def _normalize_merchant_name(self, merchant_name: str) -> str:
        """
        Normalize merchant name for matching
        
        Examples:
            "LOWES #1234" -> "lowes"
            "The Home Depot Store 5678" -> "the home depot"
            "STAPLES, INC." -> "staples inc"
        """
        # Convert to lowercase
        normalized = merchant_name.lower()
        
        # Remove store numbers
        normalized = re.sub(r'#\d+', '', normalized)
        normalized = re.sub(r'\bstore\s+\d+\b', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\d{3,}', '', normalized)  # Remove long number sequences
        
        # Remove common suffixes
        suffixes = ['inc', 'llc', 'corp', 'co', 'ltd', 'the']
        for suffix in suffixes:
            normalized = re.sub(rf'\b{suffix}\b', '', normalized, flags=re.IGNORECASE)
        
        # Remove special characters except spaces
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized.strip()
    
    def _load_keywords(self) -> Dict[str, Tuple[str, float]]:
        """Load keyword dictionary from database (with caching)"""
        if self.keyword_cache is None:
            keywords = self.db.query(CategoryKeyword).filter(
                CategoryKeyword.is_active == True
            ).all()
            
            self.keyword_cache = {
                kw.keyword.lower(): (kw.category_name, float(kw.confidence_weight))
                for kw in keywords
            }
        
        return self.keyword_cache
    
    def process_feedback(self, receipt_id: str, confirmed_category: str, 
                        user_id: str, notes: Optional[str] = None) -> bool:
        """
        Process human feedback and update knowledge base
        
        Args:
            receipt_id: Receipt identifier
            confirmed_category: Category confirmed by human
            user_id: User who provided feedback
            notes: Optional feedback notes
        
        Returns:
            True if successful
        """
        try:
            # Get the receipt and prediction
            receipt = self.db.query(Receipt).filter(
                Receipt.receipt_id == receipt_id
            ).first()
            
            if not receipt:
                return False
            
            prediction = self.db.query(CategorizationPrediction).filter(
                CategorizationPrediction.receipt_id == receipt_id
            ).first()
            
            if not prediction:
                return False
            
            # Update prediction
            prediction.confirmed_category = confirmed_category
            prediction.is_confirmed = True
            prediction.reviewed_by = user_id
            prediction.reviewed_at = datetime.utcnow()
            
            was_correct = (prediction.predicted_category == confirmed_category)
            
            # Log feedback
            feedback = FeedbackLog(
                receipt_id=receipt_id,
                user_id=user_id,
                predicted_category=prediction.predicted_category,
                confirmed_category=confirmed_category,
                was_correct=was_correct,
                feedback_notes=notes
            )
            self.db.add(feedback)
            
            # Update merchant knowledge
            self._update_merchant_knowledge(
                receipt.merchant_name,
                confirmed_category,
                was_correct
            )
            
            self.db.commit()
            
            # Clear cache to reload updated data
            self.keyword_cache = None
            self.merchant_cache = None
            
            return True
            
        except Exception as e:
            self.db.rollback()
            print(f"Error processing feedback: {e}")
            return False
    
    def _update_merchant_knowledge(self, merchant_name: str, category: str, was_correct: bool):
        """Update merchant category knowledge base"""
        normalized = self._normalize_merchant_name(merchant_name)
        
        # Check if merchant exists
        merchant = self.db.query(MerchantCategory).filter(
            MerchantCategory.merchant_name_normalized == normalized
        ).first()
        
        if merchant:
            # Update existing merchant
            if was_correct:
                merchant.total_confirmations += 1
            else:
                merchant.total_corrections += 1
                merchant.category_name = category  # Update to correct category
            
            # Recalculate confidence
            total = merchant.total_confirmations + merchant.total_corrections
            if total > 0:
                merchant.confidence_score = merchant.total_confirmations / total
            
            merchant.updated_at = datetime.utcnow()
            
        else:
            # Add new merchant
            new_merchant = MerchantCategory(
                merchant_name=merchant_name,
                merchant_name_normalized=normalized,
                category_name=category,
                confidence_score=0.5,  # Start with moderate confidence
                total_confirmations=1 if was_correct else 0,
                total_corrections=0 if was_correct else 1
            )
            self.db.add(new_merchant)
    
    def get_stats(self) -> Dict:
        """Get categorization statistics"""
        total_predictions = self.db.query(CategorizationPrediction).count()
        confirmed = self.db.query(CategorizationPrediction).filter(
            CategorizationPrediction.is_confirmed == True
        ).count()
        
        correct = self.db.query(CategorizationPrediction).filter(
            CategorizationPrediction.is_confirmed == True,
            CategorizationPrediction.predicted_category == CategorizationPrediction.confirmed_category
        ).count()
        
        accuracy = (correct / confirmed * 100) if confirmed > 0 else 0
        
        needs_review = self.db.query(CategorizationPrediction).filter(
            CategorizationPrediction.needs_review == True,
            CategorizationPrediction.is_confirmed == False
        ).count()
        
        return {
            "total_predictions": total_predictions,
            "confirmed": confirmed,
            "correct": correct,
            "accuracy": round(accuracy, 2),
            "pending_review": needs_review
        }


# ============================================
# Testing
# ============================================

if __name__ == "__main__":
    from models import Database
    
    # Initialize database
    db = Database()
    session = db.get_session()
    
    # Create categorizer
    categorizer = ReceiptCategorizer(session)
    
    # Test categorization
    test_receipts = [
        {
            "receipt_id": "TEST001",
            "merchant_name": "LOWES #1234",
            "amount": 145.67,
            "keywords": ["lumber", "hardware"]
        },
        {
            "receipt_id": "TEST002",
            "merchant_name": "STAPLES",
            "amount": 45.30,
            "keywords": ["paper", "pens"]
        },
        {
            "receipt_id": "TEST003",
            "merchant_name": "UNKNOWN MERCHANT",
            "amount": 75.00,
            "keywords": ["hotel"]
        },
        {
            "receipt_id": "TEST004",
            "merchant_name": "HOME DEPO",  # Typo - should fuzzy match
            "amount": 200.00,
            "keywords": []
        }
    ]
    
    print("Testing Categorization Engine")
    print("=" * 50)
    
    for receipt in test_receipts:
        result = categorizer.categorize(receipt)
        print(f"\nReceipt: {receipt['merchant_name']}")
        print(f"Category: {result['category']}")
        print(f"Confidence: {result['confidence']:.2%}")
        print(f"Method: {result['method']}")
        print(f"Needs Review: {result['needs_review']}")
        print(f"Reason: {result['reason']}")
    
    # Get stats
    print("\n" + "=" * 50)
    print("System Statistics:")
    stats = categorizer.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    session.close()

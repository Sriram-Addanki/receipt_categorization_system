"""
Receipt Categorization REST API
FastAPI server with all endpoints
"""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import date, datetime
from sqlalchemy.orm import Session
import uuid

from models import (
    Database, Receipt, CategorizationPrediction, 
    IRSCategory, MerchantCategory, get_db_session
)
from categorizer import ReceiptCategorizer

# ============================================
# Initialize FastAPI
# ============================================

app = FastAPI(
    title="Receipt Categorization API",
    description="Intelligent IRS category assignment for business receipts",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db = Database()
db.create_tables()

# ============================================
# Pydantic Models (Request/Response)
# ============================================

class ReceiptData(BaseModel):
    """Receipt data from OCR extraction"""
    user_id: str = Field(..., description="User identifier")
    merchant_name: str = Field(..., description="Merchant name from receipt")
    merchant_address: Optional[str] = Field(None, description="Merchant address")
    total_amount: float = Field(..., gt=0, description="Total amount")
    tax_amount: Optional[float] = Field(None, ge=0)
    subtotal: Optional[float] = Field(None, ge=0)
    transaction_date: date = Field(..., description="Transaction date")
    payment_method: Optional[str] = Field(None, description="Payment method")
    keywords: Optional[List[str]] = Field(default_factory=list, description="Keywords from receipt")
    description: Optional[str] = Field(None, description="Additional description")
    line_items: Optional[List[Dict]] = Field(default_factory=list, description="Line items from receipt")
    receipt_data: Optional[Dict] = Field(None, description="Full OCR data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "USER123",
                "merchant_name": "LOWES #1234",
                "total_amount": 145.67,
                "tax_amount": 11.23,
                "transaction_date": "2026-03-01",
                "payment_method": "Credit Card",
                "keywords": ["lumber", "hardware", "tools"]
            }
        }


class CategorizationResponse(BaseModel):
    """Categorization result"""
    receipt_id: str
    category: str
    confidence: float
    needs_review: bool
    method: str
    reason: str
    receipt_data: Optional[Dict] = None


class FeedbackRequest(BaseModel):
    """Human feedback on categorization"""
    receipt_id: str = Field(..., description="Receipt identifier")
    confirmed_category: str = Field(..., description="Category confirmed by user")
    user_id: str = Field(..., description="User providing feedback")
    notes: Optional[str] = Field(None, description="Optional notes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "receipt_id": "REC_123",
                "confirmed_category": "Office Supplies",
                "user_id": "USER123",
                "notes": "Correction: should be office supplies"
            }
        }


class StatsResponse(BaseModel):
    """System statistics"""
    total_predictions: int
    confirmed: int
    correct: int
    accuracy: float
    pending_review: int


# ============================================
# API Endpoints
# ============================================

@app.get("/", tags=["Health"])
def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Receipt Categorization API",
        "version": "1.0.0"
    }


@app.post("/categorize", response_model=CategorizationResponse, tags=["Categorization"])
def categorize_receipt(
    receipt_data: ReceiptData,
    db_session: Session = Depends(get_db_session)
):
    """
    Categorize a receipt
    
    This is the main endpoint that processes a receipt and assigns an IRS category.
    
    **Process:**
    1. Receipt data is received from OCR extraction
    2. System attempts to categorize using rules
    3. Returns category with confidence score
    4. Flags for human review if confidence is low
    
    **Returns:**
    - category: IRS category name
    - confidence: 0.0 to 1.0 (higher is better)
    - needs_review: true if human review recommended
    - method: How category was determined
    - reason: Explanation of categorization
    """
    try:
        # Generate receipt ID
        receipt_id = f"REC_{uuid.uuid4().hex[:12].upper()}"
        
        # Create receipt record
        receipt = Receipt(
            receipt_id=receipt_id,
            user_id=receipt_data.user_id,
            merchant_name=receipt_data.merchant_name,
            merchant_address=receipt_data.merchant_address,
            total_amount=receipt_data.total_amount,
            tax_amount=receipt_data.tax_amount,
            subtotal=receipt_data.subtotal,
            transaction_date=receipt_data.transaction_date,
            payment_method=receipt_data.payment_method,
            receipt_data=receipt_data.receipt_data or {}
        )
        db_session.add(receipt)
        db_session.flush()
        
        # Prepare data for categorizer
        categorizer_input = {
            "receipt_id": receipt_id,
            "merchant_name": receipt_data.merchant_name,
            "amount": receipt_data.total_amount,
            "transaction_date": str(receipt_data.transaction_date),
            "keywords": receipt_data.keywords or [],
            "description": receipt_data.description or "",
            "line_items": receipt_data.line_items or []
        }
        
        # Categorize
        categorizer = ReceiptCategorizer(db_session)
        result = categorizer.categorize(categorizer_input)
        
        # Save prediction
        prediction = CategorizationPrediction(
            receipt_id=receipt_id,
            predicted_category=result["category"],
            confidence_score=result["confidence"],
            prediction_method=result["method"],
            needs_review=result["needs_review"],
            prediction_reason=result["reason"]
        )
        db_session.add(prediction)
        db_session.commit()
        
        # Return result
        return CategorizationResponse(
            receipt_id=receipt_id,
            category=result["category"],
            confidence=result["confidence"],
            needs_review=result["needs_review"],
            method=result["method"],
            reason=result["reason"],
            receipt_data=receipt.to_dict()
        )
        
    except Exception as e:
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Categorization failed: {str(e)}"
        )


@app.post("/feedback", tags=["Learning"])
def submit_feedback(
    feedback: FeedbackRequest,
    db_session: Session = Depends(get_db_session)
):
    """
    Submit human feedback on categorization
    
    This endpoint processes user confirmations/corrections and updates the system.
    
    **Learning Process:**
    1. User confirms or corrects the category
    2. System updates merchant knowledge base
    3. Confidence scores are recalculated
    4. Future predictions improve
    
    **Example:**
    If user confirms "LOWES → Repairs & Maintenance" is correct,
    the system increases confidence for all LOWES receipts in the future.
    """
    try:
        categorizer = ReceiptCategorizer(db_session)
        
        success = categorizer.process_feedback(
            receipt_id=feedback.receipt_id,
            confirmed_category=feedback.confirmed_category,
            user_id=feedback.user_id,
            notes=feedback.notes
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Receipt {feedback.receipt_id} not found"
            )
        
        return {
            "status": "success",
            "message": "Feedback processed successfully",
            "receipt_id": feedback.receipt_id,
            "learned": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Feedback processing failed: {str(e)}"
        )


@app.get("/receipts/pending-review", tags=["Review"])
def get_pending_review(
    limit: int = 10,
    db_session: Session = Depends(get_db_session)
):
    """
    Get receipts that need human review
    
    Returns receipts where:
    - Confidence score is low (< 0.7)
    - Not yet confirmed by human
    - Sorted by oldest first
    """
    pending = db_session.query(
        Receipt, CategorizationPrediction
    ).join(
        CategorizationPrediction,
        Receipt.receipt_id == CategorizationPrediction.receipt_id
    ).filter(
        CategorizationPrediction.needs_review == True,
        CategorizationPrediction.is_confirmed == False
    ).order_by(
        Receipt.created_at.asc()
    ).limit(limit).all()
    
    results = []
    for receipt, prediction in pending:
        results.append({
            "receipt": receipt.to_dict(),
            "prediction": prediction.to_dict()
        })
    
    return {
        "count": len(results),
        "receipts": results
    }


@app.get("/receipts/{receipt_id}", tags=["Receipts"])
def get_receipt(
    receipt_id: str,
    db_session: Session = Depends(get_db_session)
):
    """Get receipt details by ID"""
    receipt = db_session.query(Receipt).filter(
        Receipt.receipt_id == receipt_id
    ).first()
    
    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Receipt {receipt_id} not found"
        )
    
    prediction = db_session.query(CategorizationPrediction).filter(
        CategorizationPrediction.receipt_id == receipt_id
    ).first()
    
    return {
        "receipt": receipt.to_dict(),
        "prediction": prediction.to_dict() if prediction else None
    }


@app.get("/categories", tags=["Categories"])
def get_categories(db_session: Session = Depends(get_db_session)):
    """
    Get all IRS categories
    
    Returns the list of 14 standard IRS business expense categories.
    """
    categories = db_session.query(IRSCategory).filter(
        IRSCategory.is_active == True
    ).all()
    
    return {
        "count": len(categories),
        "categories": [cat.to_dict() for cat in categories]
    }


@app.get("/merchants", tags=["Merchants"])
def get_merchants(
    min_confidence: float = 0.0,
    limit: int = 100,
    db_session: Session = Depends(get_db_session)
):
    """
    Get merchant knowledge base
    
    Returns merchants the system has learned, sorted by confidence.
    """
    merchants = db_session.query(MerchantCategory).filter(
        MerchantCategory.confidence_score >= min_confidence
    ).order_by(
        MerchantCategory.confidence_score.desc()
    ).limit(limit).all()
    
    return {
        "count": len(merchants),
        "merchants": [m.to_dict() for m in merchants]
    }


@app.get("/stats", response_model=StatsResponse, tags=["Analytics"])
def get_stats(db_session: Session = Depends(get_db_session)):
    """
    Get system statistics
    
    Returns:
    - Total predictions made
    - Number confirmed by humans
    - Accuracy rate
    - Pending reviews
    """
    categorizer = ReceiptCategorizer(db_session)
    stats = categorizer.get_stats()
    
    return StatsResponse(**stats)


@app.get("/analytics/performance", tags=["Analytics"])
def get_performance(
    days: int = 30,
    db_session: Session = Depends(get_db_session)
):
    """
    Get performance metrics over time
    
    Returns daily accuracy, confidence, and review rate for the last N days.
    """
    from sqlalchemy import func, case
    from datetime import timedelta
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    daily_stats = db_session.query(
        func.date(CategorizationPrediction.created_at).label('date'),
        func.count(CategorizationPrediction.id).label('total'),
        func.avg(CategorizationPrediction.confidence_score).label('avg_confidence'),
        func.sum(
            case(
                (CategorizationPrediction.needs_review == True, 1),
                else_=0
            )
        ).label('needs_review'),
        func.sum(
            case(
                (CategorizationPrediction.is_confirmed == True, 1),
                else_=0
            )
        ).label('confirmed'),
        func.sum(
            case(
                ((CategorizationPrediction.is_confirmed == True) & 
                 (CategorizationPrediction.predicted_category == CategorizationPrediction.confirmed_category), 1),
                else_=0
            )
        ).label('correct')
    ).filter(
        CategorizationPrediction.created_at >= cutoff_date
    ).group_by(
        func.date(CategorizationPrediction.created_at)
    ).order_by(
        func.date(CategorizationPrediction.created_at).desc()
    ).all()
    
    results = []
    for stat in daily_stats:
        accuracy = (stat.correct / stat.confirmed * 100) if stat.confirmed > 0 else 0
        review_rate = (stat.needs_review / stat.total * 100) if stat.total > 0 else 0
        
        results.append({
            "date": str(stat.date),
            "total_predictions": stat.total,
            "avg_confidence": round(float(stat.avg_confidence), 4) if stat.avg_confidence else 0,
            "review_rate": round(review_rate, 2),
            "confirmed": stat.confirmed,
            "correct": stat.correct,
            "accuracy": round(accuracy, 2)
        })
    
    return {
        "days": days,
        "data": results
    }


@app.delete("/receipts/{receipt_id}", tags=["Receipts"])
def delete_receipt(
    receipt_id: str,
    db_session: Session = Depends(get_db_session)
):
    """Delete a receipt and its prediction"""
    # Delete prediction first (foreign key)
    db_session.query(CategorizationPrediction).filter(
        CategorizationPrediction.receipt_id == receipt_id
    ).delete()
    
    # Delete receipt
    deleted = db_session.query(Receipt).filter(
        Receipt.receipt_id == receipt_id
    ).delete()
    
    db_session.commit()
    
    if deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Receipt {receipt_id} not found"
        )
    
    return {"status": "success", "message": "Receipt deleted"}


# ============================================
# Run Server
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    print("Starting Receipt Categorization API Server...")
    print("API Documentation: http://localhost:8000/docs")
    print("Alternative docs: http://localhost:8000/redoc")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes
        log_level="info"
    )

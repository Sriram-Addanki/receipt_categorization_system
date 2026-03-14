"""
Simple Demo Script
Test the categorization system with sample receipts
"""
import requests
import json
from datetime import date

API_URL = "http://localhost:8000"

def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def categorize_receipt(receipt_data):
    """Send receipt for categorization"""
    response = requests.post(f"{API_URL}/categorize", json=receipt_data)
    return response.json()

def submit_feedback(receipt_id, category, user_id):
    """Submit human feedback"""
    feedback_data = {
        "receipt_id": receipt_id,
        "confirmed_category": category,
        "user_id": user_id
    }
    response = requests.post(f"{API_URL}/feedback", json=feedback_data)
    return response.json()

def get_stats():
    """Get system statistics"""
    response = requests.get(f"{API_URL}/stats")
    return response.json()

def main():
    print_header("Receipt Categorization System - Demo")
    
    # Test receipts
    test_receipts = [
        {
            "user_id": "DEMO_USER",
            "merchant_name": "LOWES #1234",
            "total_amount": 145.67,
            "transaction_date": str(date.today()),
            "keywords": ["lumber", "hardware", "tools"],
            "description": "Purchased lumber and tools for repairs"
        },
        {
            "user_id": "DEMO_USER",
            "merchant_name": "STAPLES",
            "total_amount": 45.30,
            "transaction_date": str(date.today()),
            "keywords": ["paper", "pens", "office"],
            "description": "Office supplies"
        },
        {
            "user_id": "DEMO_USER",
            "merchant_name": "DELTA AIRLINES",
            "total_amount": 456.00,
            "transaction_date": str(date.today()),
            "keywords": ["flight", "travel"],
            "description": "Business trip to NYC"
        },
        {
            "user_id": "DEMO_USER",
            "merchant_name": "UNKNOWN RESTAURANT",
            "total_amount": 75.50,
            "transaction_date": str(date.today()),
            "keywords": ["dinner", "client"],
            "description": "Client dinner meeting"
        },
        {
            "user_id": "DEMO_USER",
            "merchant_name": "COMPLETELY UNKNOWN MERCHANT",
            "total_amount": 123.45,
            "transaction_date": str(date.today()),
            "keywords": [],
            "description": "Unknown purchase"
        }
    ]
    
    print("\nCategorizing receipts...\n")
    
    results = []
    
    for i, receipt in enumerate(test_receipts, 1):
        print(f"\nReceipt {i}: {receipt['merchant_name']}")
        print(f"Amount: ${receipt['total_amount']}")
        
        # Categorize
        result = categorize_receipt(receipt)
        results.append(result)
        
        print(f"→ Category: {result['category']}")
        print(f"→ Confidence: {result['confidence']:.2%}")
        print(f"→ Method: {result['method']}")
        print(f"→ Needs Review: {result['needs_review']}")
        print(f"→ Reason: {result['reason']}")
        
        # Simulate human confirmation
        if result['needs_review']:
            print(f"→ Human Review: Confirming category...")
            feedback = submit_feedback(
                result['receipt_id'],
                result['category'],
                "DEMO_USER"
            )
            print(f"→ Feedback: {feedback['message']}")
    
    # Get final statistics
    print_header("System Statistics")
    stats = get_stats()
    print(f"\nTotal Predictions: {stats['total_predictions']}")
    print(f"Confirmed: {stats['confirmed']}")
    print(f"Correct: {stats['correct']}")
    print(f"Accuracy: {stats['accuracy']}%")
    print(f"Pending Review: {stats['pending_review']}")
    
    print_header("Demo Complete")
    print("\nKey Takeaways:")
    print("1. Known merchants (LOWES, STAPLES, DELTA) → High confidence, no review")
    print("2. Keywords help categorize unknown merchants")
    print("3. System learns from human feedback")
    print("4. Accuracy improves with each confirmation\n")
    
    print("Next Steps:")
    print("1. Open http://localhost:8080/review.html to review receipts")
    print("2. Open http://localhost:8000/docs for API documentation")
    print("3. Try your own receipts via API\n")

if __name__ == "__main__":
    try:
        # Check if API is running
        response = requests.get(API_URL)
        if response.status_code == 200:
            main()
        else:
            print("Error: API is not responding correctly")
            print("Please make sure the API is running: python backend/api.py")
    except requests.exceptions.ConnectionError:
        print("Error: Cannot connect to API")
        print("Please start the API server first: python backend/api.py")

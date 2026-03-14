# 🚀 Quick Start Guide
## Receipt Categorization System

**Get up and running in 5 minutes!**

---

## Prerequisites

Before you start, make sure you have:

- ✅ Python 3.9 or higher
- ✅ PostgreSQL 12 or higher
- ✅ Git (optional, if cloning from repository)

---

## Step 1: Install PostgreSQL

### macOS (with Homebrew)
```bash
brew install postgresql@15
brew services start postgresql@15
```

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Windows
Download and install from: https://www.postgresql.org/download/windows/

---

## Step 2: Set Up Database

```bash
# Create database
createdb receipt_categorization

# Or using psql:
psql -U postgres
CREATE DATABASE receipt_categorization;
\q

# Load schema
psql -d receipt_categorization -f database/schema.sql
```

---

## Step 3: Set Up Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Step 4: Configure Environment

```bash
# Copy environment template
cp config/.env.template .env

# Edit .env file
nano .env  # or use your favorite editor

# Update DATABASE_URL if needed:
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/receipt_categorization
```

---

## Step 5: Start the API Server

```bash
cd backend
python api.py
```

You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

**API is now running at:** http://localhost:8000  
**API Docs:** http://localhost:8000/docs

---

## Step 6: Open the Review UI

In a NEW terminal:

```bash
cd frontend
python -m http.server 8080
```

**Review UI is now at:** http://localhost:8080/review.html

---

## Step 7: Test the System

In a NEW terminal:

```bash
# Run demo script
python demo.py
```

This will:
1. Send 5 test receipts to the API
2. Show categorization results
3. Simulate human feedback
4. Display system statistics

---

## Using the System

### Option 1: Web UI

1. Open http://localhost:8080/review.html
2. Review predicted categories
3. Confirm correct or fix incorrect predictions
4. Watch accuracy improve!

### Option 2: API (via curl)

```bash
# Categorize a receipt
curl -X POST "http://localhost:8000/categorize" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "USER123",
    "merchant_name": "LOWES #1234",
    "total_amount": 145.67,
    "transaction_date": "2026-03-01",
    "keywords": ["lumber", "hardware"]
  }'

# Submit feedback
curl -X POST "http://localhost:8000/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "receipt_id": "REC_ABC123",
    "confirmed_category": "Repairs & Maintenance",
    "user_id": "USER123"
  }'

# Get statistics
curl "http://localhost:8000/stats"
```

### Option 3: API (via Python)

```python
import requests

# Categorize
response = requests.post("http://localhost:8000/categorize", json={
    "user_id": "USER123",
    "merchant_name": "STAPLES",
    "total_amount": 45.30,
    "transaction_date": "2026-03-01",
    "keywords": ["paper", "pens"]
})

result = response.json()
print(f"Category: {result['category']}")
print(f"Confidence: {result['confidence']:.2%}")
```

---

## Troubleshooting

### Database Connection Error

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql  # Linux
brew services list               # macOS

# Test connection
psql -d receipt_categorization -U postgres
```

### Import Errors

```bash
# Make sure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Port Already in Use

```bash
# Check what's using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process or use different port
python api.py  # Edit api.py to change port if needed
```

### CORS Error in Browser

Update `.env` file:
```
ALLOWED_ORIGINS=http://localhost:8080,http://localhost:3000
```

Restart API server.

---

## Docker Alternative (Even Faster!)

If you have Docker installed:

```bash
# Start everything with one command
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

Services:
- API: http://localhost:8000
- UI: http://localhost:8080
- Database: localhost:5432

---

## Next Steps

1. ✅ **Test with Real Data**
   - Send your actual receipt data to the API
   - Review and confirm categories
   - Watch the system learn!

2. ✅ **Integrate with Your App**
   - Use the REST API endpoints
   - See API docs at http://localhost:8000/docs
   - Check code examples in README.md

3. ✅ **Customize**
   - Add more merchants to seed data
   - Add more keywords to `category_keywords` table
   - Adjust confidence thresholds in `.env`

4. ✅ **Monitor Performance**
   - Check `/stats` endpoint
   - Use `/analytics/performance` for trends
   - Review `/merchants` to see learned patterns

---

## Quick Commands Reference

```bash
# Start API
cd backend && python api.py

# Start UI
cd frontend && python -m http.server 8080

# Run tests
pytest tests/ -v

# Run demo
python demo.py

# Check stats
curl http://localhost:8000/stats

# View API docs
open http://localhost:8000/docs
```

---

## Support

- 📖 Full documentation: See README.md
- 🐛 Issues: Open a GitHub issue
- 📧 Email: support@yourcompany.com

---

**You're all set! 🎉**

The system is ready to categorize receipts and learn from your feedback.

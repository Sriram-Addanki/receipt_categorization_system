-- Receipt Categorization System Database Schema
-- PostgreSQL Database Setup

-- Create database (run this separately)
-- CREATE DATABASE receipt_categorization;

-- Connect to the database
-- \c receipt_categorization;

-- ============================================
-- 1. IRS Categories Table
-- ============================================
CREATE TABLE IF NOT EXISTS irs_categories (
    id SERIAL PRIMARY KEY,
    category_name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    parent_category VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert IRS standard categories
INSERT INTO irs_categories (category_name, description, parent_category) VALUES
    ('Office Supplies', 'Office materials, stationery, equipment', NULL),
    ('Travel', 'Business travel expenses including airfare, hotels, car rental', NULL),
    ('Meals & Entertainment', 'Business meals and client entertainment', NULL),
    ('Utilities', 'Electric, gas, water, internet, phone services', NULL),
    ('Rent or Lease', 'Office or equipment rental/lease payments', NULL),
    ('Advertising & Marketing', 'Marketing, advertising, promotional expenses', NULL),
    ('Insurance', 'Business insurance premiums', NULL),
    ('Repairs & Maintenance', 'Equipment and building repairs', NULL),
    ('Professional Services', 'Legal, accounting, consulting fees', NULL),
    ('Taxes & Licenses', 'Business taxes and professional licenses', NULL),
    ('Vehicle Expenses', 'Vehicle operation, fuel, maintenance', NULL),
    ('Employee Wages & Benefits', 'Salaries, benefits, payroll taxes', NULL),
    ('Depreciation', 'Asset depreciation expenses', NULL),
    ('Other Business Expenses', 'Miscellaneous business expenses', NULL)
ON CONFLICT (category_name) DO NOTHING;

-- ============================================
-- 2. Merchant Categories Knowledge Base
-- ============================================
CREATE TABLE IF NOT EXISTS merchant_categories (
    id SERIAL PRIMARY KEY,
    merchant_name VARCHAR(255) NOT NULL,
    merchant_name_normalized VARCHAR(255) NOT NULL,
    category_name VARCHAR(100) NOT NULL REFERENCES irs_categories(category_name),
    confidence_score DECIMAL(5,4) DEFAULT 0.0000,
    total_confirmations INTEGER DEFAULT 0,
    total_corrections INTEGER DEFAULT 0,
    avg_amount DECIMAL(10,2),
    keywords TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(merchant_name_normalized)
);

CREATE INDEX idx_merchant_normalized ON merchant_categories(merchant_name_normalized);
CREATE INDEX idx_category_name ON merchant_categories(category_name);

-- ============================================
-- 3. Receipts Table
-- ============================================
CREATE TABLE IF NOT EXISTS receipts (
    id SERIAL PRIMARY KEY,
    receipt_id VARCHAR(50) UNIQUE NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    merchant_name VARCHAR(255) NOT NULL,
    merchant_address TEXT,
    total_amount DECIMAL(10,2) NOT NULL,
    tax_amount DECIMAL(10,2),
    subtotal DECIMAL(10,2),
    transaction_date DATE NOT NULL,
    payment_method VARCHAR(50),
    receipt_data JSONB,  -- Full receipt data from OCR
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_receipt_user ON receipts(user_id);
CREATE INDEX idx_receipt_merchant ON receipts(merchant_name);
CREATE INDEX idx_receipt_date ON receipts(transaction_date);

-- ============================================
-- 4. Categorization Predictions
-- ============================================
CREATE TABLE IF NOT EXISTS categorization_predictions (
    id SERIAL PRIMARY KEY,
    receipt_id VARCHAR(50) NOT NULL REFERENCES receipts(receipt_id),
    predicted_category VARCHAR(100) NOT NULL REFERENCES irs_categories(category_name),
    confidence_score DECIMAL(5,4) NOT NULL,
    prediction_method VARCHAR(50) NOT NULL,  -- 'exact_match', 'fuzzy_match', 'keyword', 'ml_model', 'default'
    needs_review BOOLEAN DEFAULT FALSE,
    confirmed_category VARCHAR(100) REFERENCES irs_categories(category_name),
    is_confirmed BOOLEAN DEFAULT FALSE,
    reviewed_by VARCHAR(50),
    reviewed_at TIMESTAMP,
    prediction_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_prediction_receipt ON categorization_predictions(receipt_id);
CREATE INDEX idx_prediction_confirmed ON categorization_predictions(is_confirmed);

-- ============================================
-- 5. Keywords Dictionary
-- ============================================
CREATE TABLE IF NOT EXISTS category_keywords (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(100) NOT NULL,
    category_name VARCHAR(100) NOT NULL REFERENCES irs_categories(category_name),
    confidence_weight DECIMAL(3,2) DEFAULT 0.50,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_keyword ON category_keywords(keyword);

-- Insert common keywords
INSERT INTO category_keywords (keyword, category_name, confidence_weight) VALUES
    -- Office Supplies
    ('staples', 'Office Supplies', 0.90),
    ('office depot', 'Office Supplies', 0.90),
    ('paper', 'Office Supplies', 0.70),
    ('pens', 'Office Supplies', 0.80),
    ('printer', 'Office Supplies', 0.85),
    ('ink', 'Office Supplies', 0.75),
    ('desk', 'Office Supplies', 0.70),
    ('chair', 'Office Supplies', 0.70),
    
    -- Travel
    ('hotel', 'Travel', 0.90),
    ('airbnb', 'Travel', 0.85),
    ('flight', 'Travel', 0.95),
    ('airline', 'Travel', 0.95),
    ('delta', 'Travel', 0.90),
    ('united', 'Travel', 0.90),
    ('american airlines', 'Travel', 0.90),
    ('uber', 'Travel', 0.70),
    ('lyft', 'Travel', 0.70),
    ('rental car', 'Travel', 0.85),
    ('hertz', 'Travel', 0.85),
    
    -- Meals & Entertainment
    ('restaurant', 'Meals & Entertainment', 0.80),
    ('cafe', 'Meals & Entertainment', 0.75),
    ('coffee', 'Meals & Entertainment', 0.70),
    ('lunch', 'Meals & Entertainment', 0.70),
    ('dinner', 'Meals & Entertainment', 0.70),
    ('starbucks', 'Meals & Entertainment', 0.75),
    ('mcdonald', 'Meals & Entertainment', 0.80),
    
    -- Repairs & Maintenance
    ('lowes', 'Repairs & Maintenance', 0.85),
    ('home depot', 'Repairs & Maintenance', 0.85),
    ('hardware', 'Repairs & Maintenance', 0.80),
    ('lumber', 'Repairs & Maintenance', 0.75),
    ('repair', 'Repairs & Maintenance', 0.85),
    ('maintenance', 'Repairs & Maintenance', 0.85),
    
    -- Utilities
    ('electric', 'Utilities', 0.90),
    ('gas company', 'Utilities', 0.90),
    ('water', 'Utilities', 0.85),
    ('internet', 'Utilities', 0.85),
    ('phone', 'Utilities', 0.75),
    ('comcast', 'Utilities', 0.80),
    ('verizon', 'Utilities', 0.75),
    ('at&t', 'Utilities', 0.75),
    
    -- Professional Services
    ('attorney', 'Professional Services', 0.90),
    ('lawyer', 'Professional Services', 0.90),
    ('accountant', 'Professional Services', 0.90),
    ('consultant', 'Professional Services', 0.85),
    ('legal', 'Professional Services', 0.85)
ON CONFLICT DO NOTHING;

-- ============================================
-- 6. System Metrics & Monitoring
-- ============================================
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    total_predictions INTEGER DEFAULT 0,
    confirmed_predictions INTEGER DEFAULT 0,
    accuracy_rate DECIMAL(5,4),
    avg_confidence DECIMAL(5,4),
    review_rate DECIMAL(5,4),
    predictions_by_method JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_date)
);

-- ============================================
-- 7. User Feedback Log
-- ============================================
CREATE TABLE IF NOT EXISTS feedback_log (
    id SERIAL PRIMARY KEY,
    receipt_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    predicted_category VARCHAR(100),
    confirmed_category VARCHAR(100),
    was_correct BOOLEAN,
    feedback_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_feedback_receipt ON feedback_log(receipt_id);
CREATE INDEX idx_feedback_date ON feedback_log(created_at);

-- ============================================
-- 8. Functions and Triggers
-- ============================================

-- Function to update merchant confidence
CREATE OR REPLACE FUNCTION update_merchant_confidence()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_confirmed = TRUE THEN
        UPDATE merchant_categories
        SET 
            total_confirmations = total_confirmations + CASE 
                WHEN NEW.predicted_category = NEW.confirmed_category THEN 1 
                ELSE 0 
            END,
            total_corrections = total_corrections + CASE 
                WHEN NEW.predicted_category != NEW.confirmed_category THEN 1 
                ELSE 0 
            END,
            confidence_score = (total_confirmations + CASE WHEN NEW.predicted_category = NEW.confirmed_category THEN 1 ELSE 0 END)::DECIMAL / 
                              NULLIF((total_confirmations + total_corrections + 1), 0),
            category_name = NEW.confirmed_category,
            updated_at = CURRENT_TIMESTAMP
        WHERE merchant_name_normalized = lower(regexp_replace(
            (SELECT merchant_name FROM receipts WHERE receipt_id = NEW.receipt_id),
            '[^a-zA-Z0-9\s]', '', 'g'
        ));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for merchant learning
CREATE TRIGGER trigger_update_merchant_confidence
AFTER UPDATE OF is_confirmed ON categorization_predictions
FOR EACH ROW
WHEN (NEW.is_confirmed = TRUE)
EXECUTE FUNCTION update_merchant_confidence();

-- ============================================
-- 9. Seed Common Merchants
-- ============================================
INSERT INTO merchant_categories (merchant_name, merchant_name_normalized, category_name) VALUES
    ('LOWES', 'lowes', 'Repairs & Maintenance'),
    ('HOME DEPOT', 'home depot', 'Repairs & Maintenance'),
    ('STAPLES', 'staples', 'Office Supplies'),
    ('OFFICE DEPOT', 'office depot', 'Office Supplies'),
    ('DELTA AIRLINES', 'delta airlines', 'Travel'),
    ('UNITED AIRLINES', 'united airlines', 'Travel'),
    ('MARRIOTT', 'marriott', 'Travel'),
    ('HILTON', 'hilton', 'Travel'),
    ('UBER', 'uber', 'Travel'),
    ('STARBUCKS', 'starbucks', 'Meals & Entertainment'),
    ('AMAZON', 'amazon', 'Office Supplies'),
    ('COMCAST', 'comcast', 'Utilities'),
    ('VERIZON', 'verizon', 'Utilities'),
    ('AT&T', 'att', 'Utilities')
ON CONFLICT (merchant_name_normalized) DO NOTHING;

-- ============================================
-- 10. Views for Analytics
-- ============================================

CREATE OR REPLACE VIEW v_categorization_performance AS
SELECT 
    DATE(created_at) as date,
    COUNT(*) as total_predictions,
    SUM(CASE WHEN is_confirmed THEN 1 ELSE 0 END) as confirmed_count,
    AVG(confidence_score) as avg_confidence,
    SUM(CASE WHEN needs_review THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) as review_rate,
    SUM(CASE WHEN is_confirmed AND predicted_category = confirmed_category THEN 1 ELSE 0 END)::DECIMAL /
        NULLIF(SUM(CASE WHEN is_confirmed THEN 1 ELSE 0 END), 0) as accuracy
FROM categorization_predictions
GROUP BY DATE(created_at)
ORDER BY date DESC;

CREATE OR REPLACE VIEW v_merchant_performance AS
SELECT 
    mc.merchant_name,
    mc.merchant_name_normalized,
    mc.category_name,
    mc.confidence_score,
    mc.total_confirmations,
    mc.total_corrections,
    mc.total_confirmations + mc.total_corrections as total_predictions,
    CASE 
        WHEN mc.total_confirmations + mc.total_corrections > 0 
        THEN mc.total_confirmations::DECIMAL / (mc.total_confirmations + mc.total_corrections)
        ELSE 0 
    END as accuracy_rate
FROM merchant_categories mc
WHERE mc.total_confirmations + mc.total_corrections > 0
ORDER BY mc.confidence_score DESC;

-- ============================================
-- Grant permissions (adjust for your user)
-- ============================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_app_user;

-- Complete!
SELECT 'Database schema created successfully!' as status;

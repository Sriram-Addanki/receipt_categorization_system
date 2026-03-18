"""
OCR Processing Module
Extracts text from receipt images using Tesseract
"""
import pytesseract
from PIL import Image
import cv2
import numpy as np
import re
from datetime import datetime
from typing import Dict, Optional, List
import io


class ReceiptOCR:
    """Process receipt images and extract structured data"""
    
    def __init__(self):
        """Initialize OCR processor"""
        # Try to set tesseract path (Windows)
        try:
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        except:
            pass  # On Mac/Linux, tesseract should be in PATH
    
    def preprocess_image(self, image_bytes: bytes) -> np.ndarray:
        """
        Preprocess image for better OCR results
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Preprocessed image as numpy array
        """
        # Convert bytes to image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to OpenCV format
        img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding to get better contrast
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
        
        return denoised
    
    def extract_text(self, image_bytes: bytes) -> str:
        """
        Extract raw text from receipt image
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Extracted text
        """
        try:
            # Preprocess image
            processed_img = self.preprocess_image(image_bytes)
            
            # Extract text using Tesseract
            text = pytesseract.image_to_string(
                processed_img,
                config='--psm 6'  # Assume uniform block of text
            )
            
            return text.strip()
            
        except Exception as e:
            raise Exception(f"OCR extraction failed: {str(e)}")
    
    def parse_receipt_data(self, text: str) -> Dict:
        """
        Parse structured data from OCR text
        
        Args:
            text: Raw OCR text
            
        Returns:
            Dictionary with extracted data
        """
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        data = {
            "merchant_name": None,
            "total_amount": None,
            "tax_amount": None,
            "subtotal": None,
            "transaction_date": None,
            "keywords": [],
            "raw_text": text,
            "line_items": []
        }
        
        # Extract merchant name (usually first few lines)
        if lines:
            data["merchant_name"] = self._extract_merchant_name(lines)
        
        # Extract amounts
        data["total_amount"] = self._extract_total_amount(text)
        data["tax_amount"] = self._extract_tax_amount(text)
        data["subtotal"] = self._extract_subtotal(text)
        
        # Extract date
        data["transaction_date"] = self._extract_date(text)
        
        # Extract keywords
        data["keywords"] = self._extract_keywords(text)
        
        # Extract line items
        data["line_items"] = self._extract_line_items(lines)
        
        return data
    
    def _extract_merchant_name(self, lines: List[str]) -> Optional[str]:
        """Extract merchant name from first few lines"""
        # Usually merchant name is in first 3 lines
        # Skip very short lines and common words
        skip_words = {'receipt', 'invoice', 'store', 'tax', 'total', 'date'}
        
        for line in lines[:5]:
            line_clean = line.lower()
            # Look for lines with reasonable length that aren't just numbers
            if (len(line) > 3 and 
                not line_clean.replace(' ', '').isdigit() and
                not any(word in line_clean for word in skip_words) and
                not re.search(r'^\d{2}[/-]\d{2}', line)):  # Not a date
                return line.upper()
        
        return lines[0].upper() if lines else None
    
    def _extract_total_amount(self, text: str) -> Optional[float]:
        """Extract total amount"""
        # Look for patterns like "TOTAL: $45.67" or "Total 45.67"
        patterns = [
            r'total[:\s]+\$?(\d+\.?\d*)',
            r'amount[:\s]+\$?(\d+\.?\d*)',
            r'balance[:\s]+\$?(\d+\.?\d*)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except:
                    continue
        
        # Fallback: find largest dollar amount
        amounts = re.findall(r'\$?(\d+\.\d{2})', text)
        if amounts:
            return max([float(a) for a in amounts])
        
        return None
    
    def _extract_tax_amount(self, text: str) -> Optional[float]:
        """Extract tax amount"""
        patterns = [
            r'tax[:\s]+\$?(\d+\.?\d*)',
            r'sales\s*tax[:\s]+\$?(\d+\.?\d*)',
            r'gst[:\s]+\$?(\d+\.?\d*)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except:
                    continue
        
        return None
    
    def _extract_subtotal(self, text: str) -> Optional[float]:
        """Extract subtotal"""
        patterns = [
            r'subtotal[:\s]+\$?(\d+\.?\d*)',
            r'sub\s*total[:\s]+\$?(\d+\.?\d*)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except:
                    continue
        
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extract transaction date"""
        # Common date patterns
        patterns = [
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # MM/DD/YYYY or DD/MM/YYYY
            r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',    # YYYY-MM-DD
            r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4})'  # Jan 15, 2024
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                # Try to parse and standardize
                try:
                    # Try different formats
                    for fmt in ['%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%m-%d-%Y', '%B %d, %Y']:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt)
                            return parsed_date.strftime('%Y-%m-%d')
                        except:
                            continue
                except:
                    pass
                
                return date_str  # Return as-is if can't parse
        
        # Default to today if no date found
        return datetime.now().strftime('%Y-%m-%d')
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords for categorization"""
        # Common receipt keywords
        keyword_patterns = {
            'office': r'\b(paper|pen|pencil|staple|folder|binder|desk|chair|office)\b',
            'hardware': r'\b(lumber|wood|nail|screw|hammer|drill|saw|tool|paint|hardware)\b',
            'travel': r'\b(hotel|flight|airline|taxi|uber|lyft|rental|lodging|accommodation)\b',
            'food': r'\b(restaurant|cafe|coffee|lunch|dinner|breakfast|food|meal)\b',
            'fuel': r'\b(gas|fuel|gasoline|diesel|petrol)\b',
            'utilities': r'\b(electric|water|gas|internet|phone|utility)\b'
        }
        
        keywords = []
        text_lower = text.lower()
        
        for category, pattern in keyword_patterns.items():
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            keywords.extend(matches)
        
        return list(set(keywords))  # Remove duplicates
    
    def _extract_line_items(self, lines: List[str]) -> List[Dict]:
        """Extract individual line items"""
        items = []
        
        # Pattern for line items: Description + Amount
        # Example: "Hammer 2 @ 15.00 30.00"
        pattern = r'(.+?)\s+(\d+\.?\d*)\s*$'
        
        for line in lines:
            # Skip lines that look like totals or headers
            if any(word in line.lower() for word in ['total', 'subtotal', 'tax', 'receipt', 'date']):
                continue
            
            # Look for items with prices
            if re.search(r'\d+\.\d{2}', line):
                match = re.search(pattern, line)
                if match:
                    items.append({
                        "description": match.group(1).strip(),
                        "amount": float(match.group(2)) if match.group(2) else None
                    })
        
        return items
    
    def process_receipt_image(self, image_bytes: bytes) -> Dict:
        """
        Complete pipeline: Extract text and parse data
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Structured receipt data
        """
        # Extract text
        raw_text = self.extract_text(image_bytes)
        
        # Parse data
        receipt_data = self.parse_receipt_data(raw_text)
        
        return receipt_data


# Test function
if __name__ == "__main__":
    ocr = ReceiptOCR()
    
    # Test with a sample image
    with open("sample_receipt.jpg", "rb") as f:
        image_bytes = f.read()
    
    result = ocr.process_receipt_image(image_bytes)
    
    print("Extracted Data:")
    for key, value in result.items():
        print(f"{key}: {value}")
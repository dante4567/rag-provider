"""
InvoiceHandler - Preprocessing for financial documents (invoices, receipts, statements)

Key challenges:
- Structured data extraction (amounts, dates, parties, items)
- Currency and number formatting (1.234,56 vs 1,234.56)
- Tax calculations and line items
- Payment terms and due dates
- Multiple languages and formats

Strategy:
- Extract structured fields (vendor, amount, date, invoice number)
- Preserve line item tables
- Normalize currency amounts
- Extract payment terms and deadlines
- Flag missing critical information
"""

import re
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal, InvalidOperation

from .base_handler import DocumentTypeHandler

logger = logging.getLogger(__name__)


class InvoiceHandler(DocumentTypeHandler):
    """Handler for financial documents (invoices, receipts, statements)"""

    # Amount patterns (various currency formats)
    AMOUNT_PATTERNS = [
        # EUR 1.234,56 or € 1.234,56
        r'(?:EUR|€|CHF)\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        # $1,234.56 or USD 1,234.56
        r'(?:USD|\$|GBP|£)\s*(\d{1,3}(?:,\d{3})*\.\d{2})',
        # Plain numbers with currency symbols
        r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*(?:EUR|€|USD|\$|CHF|GBP|£)',
    ]

    # Date patterns (various formats)
    DATE_PATTERNS = [
        r'\b(\d{2}[./]\d{2}[./]\d{4})\b',  # DD.MM.YYYY or DD/MM/YYYY
        r'\b(\d{4}-\d{2}-\d{2})\b',        # YYYY-MM-DD (ISO)
        r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})\b',  # 15 Jan 2024
    ]

    # Invoice number patterns
    INVOICE_NUMBER_PATTERNS = [
        r'(?:Invoice|Rechnung|Facture)\s*(?:No\.|Nr\.|#|Number)?:?\s*([A-Z0-9\-]+)',
        r'(?:Receipt|Quittung|Beleg)\s*(?:No\.|Nr\.|#)?:?\s*([A-Z0-9\-]+)',
    ]

    # Payment terms keywords
    PAYMENT_TERMS = [
        r'(?:due|fällig|payable)\s+(?:on|am|by|bis)?\s*(\d{1,2}[./]\d{1,2}[./]\d{4})',
        r'(?:payment|zahlung).*?(\d+)\s*(?:days|tage|jours)',
        r'(?:net|netto)\s*(\d+)',  # Net 30, Net 60
    ]

    def preprocess(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Clean invoice content:
        1. Extract structured data (amounts, dates, parties)
        2. Preserve line item tables
        3. Remove boilerplate (terms & conditions, disclaimers)
        4. Normalize formatting
        """
        original_length = len(text)

        # Preserve critical sections (line items, totals)
        # These are typically in table format with aligned columns

        # Remove lengthy terms & conditions (usually at the end)
        # Look for common section headers
        tc_patterns = [
            r'(?:Terms?\s+(?:and|&)\s+Conditions?|Allgemeine\s+Geschäftsbedingungen|AGB).*',
            r'(?:Legal\s+Notice|Rechtliche\s+Hinweise).*',
            r'(?:Privacy\s+Policy|Datenschutz).*',
        ]

        for pattern in tc_patterns:
            # Only remove if it's more than 500 chars (substantial T&C section)
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match and len(match.group(0)) > 500:
                text = text[:match.start()] + text[match.end():]
                logger.info(f"💰 Removed lengthy terms & conditions section")

        # Remove bank/payment details footer (often repeated boilerplate)
        # Keep if short (important), remove if long (boilerplate)
        bank_pattern = r'(?:Bank\s+Details?|Bankverbindung).*?(?:IBAN|BIC|Swift).*?(?:\n\n|\Z)'
        bank_match = re.search(bank_pattern, text, re.IGNORECASE | re.DOTALL)
        if bank_match and len(bank_match.group(0)) > 300:
            # Keep just the first line (usually has relevant info)
            text = text.replace(bank_match.group(0), '')

        # Clean excessive whitespace but preserve table alignment
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # If line looks like table/aligned data, preserve spacing
            if re.search(r'\s{3,}', line) and len(line.split()) >= 2:
                cleaned_lines.append(line)  # Preserve alignment
            else:
                cleaned_lines.append(' '.join(line.split()))  # Normal cleanup

        text = '\n'.join(cleaned_lines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        cleaned_length = len(text)
        retention_pct = (cleaned_length / original_length * 100) if original_length > 0 else 0

        logger.info(f"💰 Invoice cleaned: {original_length} → {cleaned_length} chars ({retention_pct:.1f}% retained)")

        return text

    def extract_metadata(self, text: str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract invoice-specific structured data:
        - Total amount
        - Invoice number
        - Invoice date
        - Due date
        - Vendor/supplier name
        - Line item count
        - Currency
        - Tax amount (VAT/MwSt)
        """
        metadata = {}

        # Extract amounts
        amounts = []
        for pattern in self.AMOUNT_PATTERNS:
            amounts.extend(re.findall(pattern, text, re.IGNORECASE))

        if amounts:
            # Largest amount is usually the total
            # Normalize to consistent format for comparison
            normalized_amounts = []
            for amt in amounts:
                try:
                    # Convert 1.234,56 to 1234.56 or 1,234.56 to 1234.56
                    normalized = amt.replace('.', '').replace(',', '.')
                    if '.' not in normalized:
                        normalized += '.00'
                    normalized_amounts.append(float(normalized))
                except (ValueError, InvalidOperation):
                    continue

            if normalized_amounts:
                total_amount = max(normalized_amounts)
                metadata['total_amount'] = total_amount
                metadata['currency'] = self._detect_currency(text)

        # Extract invoice number
        for pattern in self.INVOICE_NUMBER_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata['invoice_number'] = match.group(1)
                break

        # Extract dates
        dates = []
        for pattern in self.DATE_PATTERNS:
            dates.extend(re.findall(pattern, text))

        if dates:
            # First date is usually invoice date, last might be due date
            metadata['invoice_date'] = dates[0]
            if len(dates) > 1:
                metadata['due_date'] = dates[-1]

        # Extract payment terms
        for pattern in self.PAYMENT_TERMS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata['payment_terms'] = match.group(0)
                break

        # Detect vendor/supplier (usually in header, look for "From:" or company name)
        vendor_patterns = [
            r'(?:From|Von|De):?\s*([A-Z][A-Za-z\s&\.]+(?:GmbH|LLC|Ltd|Inc|AG|SA)?)',
            r'^([A-Z][A-Za-z\s&\.]+(?:GmbH|LLC|Ltd|Inc|AG|SA))',  # First line company name
        ]
        for pattern in vendor_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                vendor = match.group(1).strip()
                if len(vendor) > 3 and len(vendor) < 100:  # Reasonable length
                    metadata['vendor'] = vendor
                    break

        # Count line items (rows with amount + description pattern)
        line_item_pattern = r'.+\s+\d+[.,]\d{2}'
        line_items = re.findall(line_item_pattern, text)
        metadata['line_item_count'] = len(line_items)

        # Extract tax/VAT
        tax_patterns = [
            r'(?:VAT|MwSt|Tax|Steuer).*?(\d+[.,]\d{2})',
            r'(\d+)%\s*(?:VAT|MwSt)',
        ]
        for pattern in tax_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata['tax_info'] = match.group(0)
                break

        return metadata

    def _detect_currency(self, text: str) -> str:
        """Detect currency from symbols/codes"""
        currencies = {
            'EUR': r'EUR|€',
            'USD': r'USD|\$',
            'GBP': r'GBP|£',
            'CHF': r'CHF',
        }

        for currency, pattern in currencies.items():
            if re.search(pattern, text):
                return currency

        return 'UNKNOWN'

    def get_chunking_strategy(self, metadata: Dict[str, Any]) -> str:
        """
        Invoices should usually be kept whole:
        - Short documents
        - Structured data
        - Context matters (line items relate to total)
        """
        line_item_count = metadata.get('line_item_count', 0)

        if line_item_count > 50:
            return 'section'  # Very long invoice, split by sections
        else:
            return 'whole'  # Keep invoice intact

    def get_summary_prompt(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Invoice summaries should capture:
        1. Vendor/supplier
        2. Total amount and currency
        3. Invoice date and due date
        4. What was purchased (main items)
        5. Payment status if mentioned
        """
        has_amount = 'total_amount' in metadata
        has_vendor = 'vendor' in metadata
        has_due_date = 'due_date' in metadata

        prompt = """2-3 sentence summary capturing:
   - Vendor/supplier name and type of business"""

        if has_amount:
            prompt += f"\n   - Total amount: {metadata.get('currency', '')} {metadata.get('total_amount', '')}"

        prompt += "\n   - Invoice date"

        if has_due_date:
            prompt += " and payment due date"

        prompt += "\n   - Main items or services purchased (be specific)"

        if metadata.get('line_item_count', 0) > 10:
            prompt += "\n   - Number of line items and general categories"

        prompt += "\n   - Any important reference numbers or terms"

        return prompt

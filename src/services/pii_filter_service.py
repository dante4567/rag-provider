"""
PII (Personally Identifiable Information) Filtering Service

Detects and redacts sensitive information before indexing:
- Email addresses
- Phone numbers
- Social Security Numbers (SSN)
- Credit card numbers
- IP addresses
- Dates of birth

Critical for privacy compliance (GDPR, HIPAA, etc.)
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PIIType(str, Enum):
    """Types of PII that can be detected"""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"
    IBAN = "iban"
    PASSPORT = "passport"


@dataclass
class PIIMatch:
    """A detected PII instance"""
    pii_type: PIIType
    value: str  # Original value
    start: int  # Character offset
    end: int
    confidence: float  # 0.0-1.0


class PIIFilterService:
    """
    Service for detecting and redacting PII from text.

    Usage:
        filter = PIIFilterService()

        # Detect only
        detected = filter.detect(text)

        # Redact
        clean_text, detected = filter.redact(text)

        # Check if text has PII
        has_pii = filter.has_pii(text)
    """

    # Regex patterns for PII detection
    PATTERNS = {
        PIIType.EMAIL: [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        ],
        PIIType.PHONE: [
            # US formats: (123) 456-7890, 123-456-7890, 123.456.7890, 1234567890
            r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
            # International: +49 123 456789, +44 20 1234 5678
            r'\+[0-9]{1,3}[\s.-]?[0-9]{2,3}[\s.-]?[0-9]{3,4}[\s.-]?[0-9]{3,4}',
            # German: 0123 456789, 0123/456789
            r'\b0[0-9]{3,4}[\s/.-]?[0-9]{6,8}\b'
        ],
        PIIType.SSN: [
            # US SSN: 123-45-6789
            r'\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b'
        ],
        PIIType.CREDIT_CARD: [
            # Common formats: 1234 5678 9012 3456, 1234-5678-9012-3456
            r'\b[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}\b',
            # Amex: 3782 822463 10005
            r'\b3[47][0-9]{13}\b'
        ],
        PIIType.IP_ADDRESS: [
            # IPv4: 192.168.1.1
            r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
            # IPv6: 2001:0db8:85a3:0000:0000:8a2e:0370:7334
            r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'
        ],
        PIIType.DATE_OF_BIRTH: [
            # DOB in common contexts: "DOB: 01/15/1990", "Born: 1990-01-15"
            r'(?:DOB|Date of Birth|Born|Birthday)[\s:]+([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4}|[0-9]{4}[/-][0-9]{1,2}[/-][0-9]{1,2})'
        ],
        PIIType.IBAN: [
            # European IBAN: DE89 3704 0044 0532 0130 00
            r'\b[A-Z]{2}[0-9]{2}[\s]?[0-9]{4}[\s]?[0-9]{4}[\s]?[0-9]{4}[\s]?[0-9]{4}[\s]?[0-9]{0,2}\b'
        ],
        PIIType.PASSPORT: [
            # US Passport: 123456789
            r'\b[A-Z]{1,2}[0-9]{6,9}\b'
        ]
    }

    # Validation functions (reduce false positives)
    @staticmethod
    def is_valid_luhn(number: str) -> bool:
        """Luhn algorithm for credit card validation"""
        digits = [int(d) for d in number if d.isdigit()]
        checksum = 0
        for i, digit in enumerate(reversed(digits)):
            if i % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit
        return checksum % 10 == 0

    @staticmethod
    def is_valid_ssn(ssn: str) -> bool:
        """Basic SSN validation (not 000, 666, 900-999 in first group)"""
        parts = ssn.split('-')
        if len(parts) != 3:
            return False
        area = int(parts[0])
        # Invalid SSN patterns
        if area == 0 or area == 666 or area >= 900:
            return False
        return True

    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """Validate IPv4 address"""
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False

    def __init__(
        self,
        enabled_types: Optional[List[PIIType]] = None,
        redaction_mode: str = "mask",  # "mask", "remove", "hash"
        custom_patterns: Optional[Dict[str, List[str]]] = None
    ):
        """
        Initialize PII filter.

        Args:
            enabled_types: Which PII types to detect (None = all)
            redaction_mode: How to redact ("mask", "remove", "hash")
            custom_patterns: Additional regex patterns to detect
        """
        self.enabled_types = enabled_types or list(PIIType)
        self.redaction_mode = redaction_mode
        self.patterns = self.PATTERNS.copy()

        if custom_patterns:
            for pii_type, patterns in custom_patterns.items():
                if pii_type in self.patterns:
                    self.patterns[pii_type].extend(patterns)

        logger.info(f"PII Filter initialized: types={len(self.enabled_types)}, mode={redaction_mode}")

    def detect(self, text: str) -> List[PIIMatch]:
        """
        Detect PII in text without modifying it.

        Returns:
            List of PIIMatch objects with locations and types
        """
        matches = []

        for pii_type in self.enabled_types:
            if pii_type not in self.patterns:
                continue

            for pattern in self.patterns[pii_type]:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    value = match.group(0)
                    confidence = self._calculate_confidence(pii_type, value)

                    if confidence >= 0.5:  # Threshold for detection
                        matches.append(PIIMatch(
                            pii_type=pii_type,
                            value=value,
                            start=match.start(),
                            end=match.end(),
                            confidence=confidence
                        ))

        # Sort by position
        matches.sort(key=lambda m: m.start)

        # Deduplicate overlapping matches (keep higher confidence)
        deduplicated = []
        for match in matches:
            # Check if overlaps with existing match
            overlaps = False
            for existing in deduplicated:
                if (match.start < existing.end and match.end > existing.start):
                    overlaps = True
                    # Replace if higher confidence
                    if match.confidence > existing.confidence:
                        deduplicated.remove(existing)
                        deduplicated.append(match)
                    break

            if not overlaps:
                deduplicated.append(match)

        return sorted(deduplicated, key=lambda m: m.start)

    def _calculate_confidence(self, pii_type: PIIType, value: str) -> float:
        """
        Calculate confidence that this is real PII (reduce false positives).

        Returns:
            Confidence score 0.0-1.0
        """
        # Base confidence
        confidence = 0.7

        # Apply validation checks
        if pii_type == PIIType.CREDIT_CARD:
            digits_only = re.sub(r'[\s-]', '', value)
            if len(digits_only) in [13, 14, 15, 16] and self.is_valid_luhn(digits_only):
                confidence = 0.95
            else:
                confidence = 0.3  # Likely false positive

        elif pii_type == PIIType.SSN:
            if self.is_valid_ssn(value):
                confidence = 0.9
            else:
                confidence = 0.4

        elif pii_type == PIIType.IP_ADDRESS:
            if self.is_valid_ip(value):
                confidence = 0.8
            else:
                confidence = 0.2

        elif pii_type == PIIType.EMAIL:
            # Check for common non-email patterns
            if any(domain in value.lower() for domain in ['example.com', 'test.com', 'domain.com']):
                confidence = 0.4  # Likely example email
            else:
                confidence = 0.9

        elif pii_type == PIIType.PHONE:
            # Check if it's a sequential number (false positive)
            digits = re.sub(r'\D', '', value)
            if len(set(digits)) <= 3:  # e.g., 1111111111
                confidence = 0.2
            else:
                confidence = 0.85

        return confidence

    def redact(self, text: str, mode: Optional[str] = None) -> Tuple[str, List[PIIMatch]]:
        """
        Redact PII from text.

        Args:
            text: Original text
            mode: Redaction mode override ("mask", "remove", "hash")

        Returns:
            (redacted_text, detected_pii_list)
        """
        mode = mode or self.redaction_mode
        detected = self.detect(text)

        if not detected:
            return text, []

        # Build redacted text (process from end to preserve offsets)
        redacted = text
        for match in reversed(detected):
            replacement = self._get_replacement(match, mode)
            redacted = redacted[:match.start] + replacement + redacted[match.end:]

        logger.info(f"🔒 Redacted {len(detected)} PII instances: {[m.pii_type.value for m in detected]}")

        return redacted, detected

    def _get_replacement(self, match: PIIMatch, mode: str) -> str:
        """Generate replacement text for redacted PII"""
        if mode == "mask":
            return f"[REDACTED_{match.pii_type.value.upper()}]"
        elif mode == "remove":
            return ""
        elif mode == "hash":
            import hashlib
            hash_value = hashlib.sha256(match.value.encode()).hexdigest()[:8]
            return f"[{match.pii_type.value.upper()}_{hash_value}]"
        else:
            return f"[REDACTED]"

    def has_pii(self, text: str) -> bool:
        """Quick check if text contains any PII"""
        return len(self.detect(text)) > 0

    def get_pii_summary(self, text: str) -> Dict[str, int]:
        """
        Get summary of PII types found.

        Returns:
            {"email": 2, "phone": 1, "ssn": 0, ...}
        """
        detected = self.detect(text)
        summary = {pii_type.value: 0 for pii_type in PIIType}

        for match in detected:
            summary[match.pii_type.value] += 1

        return summary


# Singleton instance
_pii_filter_service = None


def get_pii_filter_service(
    enabled_types: Optional[List[PIIType]] = None,
    redaction_mode: str = "mask"
) -> PIIFilterService:
    """Get or create PII filter service singleton"""
    global _pii_filter_service

    if _pii_filter_service is None:
        _pii_filter_service = PIIFilterService(
            enabled_types=enabled_types,
            redaction_mode=redaction_mode
        )

    return _pii_filter_service

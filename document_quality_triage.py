#!/usr/bin/env python3
"""
Document Quality Triage System
==============================

Comprehensive document quality assessment, validation, and signal/noise separation
for RAG ingestion pipeline.

Features:
1. Content quality scoring
2. OCR quality assessment with cloud fallbacks
3. Signal/noise separation
4. Semantic tag similarity detection
5. Input validation and sanitization
6. Multi-stage triage pipeline

Author: Quality Assurance Team
Date: 2025-09-27
"""

import logging
import re
import string
import math
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import hashlib
import statistics
from collections import Counter
import asyncio
import json

# Set up logging
logger = logging.getLogger(__name__)

class QualityLevel(Enum):
    """Quality assessment levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    REJECT = "reject"

class ContentType(Enum):
    """Content classification for different processing strategies"""
    STRUCTURED_TEXT = "structured_text"
    NATURAL_LANGUAGE = "natural_language"
    CODE = "code"
    DATA_TABLE = "data_table"
    CONVERSATION = "conversation"
    TECHNICAL_DOC = "technical_doc"
    NOISE = "noise"
    CORRUPTED = "corrupted"

@dataclass
class QualityMetrics:
    """Document quality assessment metrics"""
    overall_score: float  # 0-1 quality score
    quality_level: QualityLevel
    content_type: ContentType

    # Signal/noise metrics
    signal_ratio: float  # Useful content ratio
    noise_ratio: float  # Garbage/spam ratio
    readability_score: float  # Text readability

    # Content characteristics
    language_confidence: float  # Language detection confidence
    encoding_quality: float  # Text encoding quality
    structure_score: float  # Document structure quality

    # Specific quality indicators
    has_meaningful_content: bool
    has_proper_formatting: bool
    has_excessive_repetition: bool
    has_binary_corruption: bool
    has_encoding_issues: bool

    # OCR-specific metrics (if applicable)
    ocr_confidence: Optional[float] = None
    ocr_method: Optional[str] = None
    requires_ocr_retry: bool = False

    # Recommendations
    recommended_action: str = "process"  # process, retry_ocr, enhance, reject
    processing_notes: List[str] = None

    def __post_init__(self):
        if self.processing_notes is None:
            self.processing_notes = []

@dataclass
class ValidationResult:
    """Input validation result"""
    is_valid: bool
    cleaned_content: str
    validation_errors: List[str]
    security_flags: List[str]
    content_warnings: List[str]

class ContentValidator:
    """Validates and sanitizes input content"""

    def __init__(self):
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.min_content_length = 10
        self.max_content_length = 10 * 1024 * 1024  # 10MB text

        # Security patterns to detect
        self.security_patterns = [
            r'<script[^>]*>.*?</script>',  # JavaScript
            r'javascript:',  # JavaScript URLs
            r'data:.*base64',  # Base64 data URLs
            r'\\x[0-9a-fA-F]{2}',  # Hex escape sequences
            r'%[0-9a-fA-F]{2}',  # URL encoding
        ]

        # Content warning patterns
        self.warning_patterns = [
            r'password\s*[:=]\s*\S+',  # Passwords
            r'api[_-]?key\s*[:=]\s*\S+',  # API keys
            r'secret\s*[:=]\s*\S+',  # Secrets
            r'token\s*[:=]\s*\S+',  # Tokens
        ]

    def validate_and_clean(self, content: str, filename: str = None) -> ValidationResult:
        """Comprehensive content validation and cleaning"""
        errors = []
        security_flags = []
        warnings = []

        # Basic validation
        if not content:
            errors.append("Content is empty")
            return ValidationResult(False, "", errors, security_flags, warnings)

        if len(content) < self.min_content_length:
            errors.append(f"Content too short (min {self.min_content_length} chars)")

        if len(content) > self.max_content_length:
            errors.append(f"Content too long (max {self.max_content_length} chars)")
            content = content[:self.max_content_length]

        # Security validation
        for pattern in self.security_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                security_flags.append(f"Potential security risk: {pattern}")

        # Content warnings
        for pattern in self.warning_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                warnings.append(f"Sensitive data detected: {pattern}")

        # Clean content
        cleaned_content = self._clean_content(content)

        is_valid = len(errors) == 0 and len(security_flags) == 0

        return ValidationResult(
            is_valid=is_valid,
            cleaned_content=cleaned_content,
            validation_errors=errors,
            security_flags=security_flags,
            content_warnings=warnings
        )

    def _clean_content(self, content: str) -> str:
        """Advanced content cleaning"""
        # Remove null bytes and problematic control characters
        content = content.replace('\x00', '')
        content = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)

        # Handle encoding issues
        try:
            content = content.encode('utf-8', errors='ignore').decode('utf-8')
        except Exception:
            content = str(content)

        # Normalize whitespace but preserve structure
        content = re.sub(r'[ \t]+', ' ', content)  # Multiple spaces/tabs to single space
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Multiple newlines to double

        return content.strip()

class OCRQualityAssessment:
    """Assesses OCR quality and manages cloud fallbacks"""

    def __init__(self):
        self.confidence_threshold = 0.7
        self.cloud_providers = ['google', 'azure', 'aws']  # Priority order

    def assess_ocr_quality(self, text: str, confidence_data: Dict = None) -> Tuple[float, bool]:
        """Assess OCR text quality and determine if retry needed"""
        if not text or not text.strip():
            return 0.0, True

        # Use confidence data if available (from pytesseract)
        if confidence_data:
            avg_confidence = confidence_data.get('avg_confidence', 0.0)
            if avg_confidence < self.confidence_threshold:
                return avg_confidence / 100.0, True

        # Heuristic quality assessment
        quality_score = self._calculate_text_quality(text)
        needs_retry = quality_score < 0.6

        return quality_score, needs_retry

    def _calculate_text_quality(self, text: str) -> float:
        """Calculate OCR text quality using heuristics"""
        if not text:
            return 0.0

        # Metrics for OCR quality
        char_count = len(text)
        word_count = len(text.split())

        # Character quality indicators
        alpha_ratio = sum(1 for c in text if c.isalpha()) / char_count
        digit_ratio = sum(1 for c in text if c.isdigit()) / char_count
        punct_ratio = sum(1 for c in text if c in string.punctuation) / char_count
        space_ratio = sum(1 for c in text if c.isspace()) / char_count
        garbage_ratio = sum(1 for c in text if ord(c) > 127 and not c.isalpha()) / char_count

        # Word quality indicators
        avg_word_length = statistics.mean(len(word) for word in text.split()) if word_count > 0 else 0
        very_short_words = sum(1 for word in text.split() if len(word) <= 2) / max(word_count, 1)
        very_long_words = sum(1 for word in text.split() if len(word) >= 20) / max(word_count, 1)

        # Calculate quality score
        quality_factors = [
            min(1.0, alpha_ratio * 2),  # Good ratio of alphabetic characters
            max(0.0, 1.0 - garbage_ratio * 5),  # Low garbage characters
            max(0.0, 1.0 - very_short_words * 2),  # Not too many very short words
            max(0.0, 1.0 - very_long_words * 3),  # Not too many very long words
            min(1.0, avg_word_length / 5.0),  # Reasonable average word length
            min(1.0, space_ratio * 5),  # Reasonable spacing
        ]

        quality_score = statistics.mean(quality_factors)

        # Penalty for suspicious patterns
        if re.search(r'[a-zA-Z]{30,}', text):  # Very long character sequences
            quality_score *= 0.7
        if re.search(r'(.)\1{10,}', text):  # Repeated characters
            quality_score *= 0.5

        return max(0.0, min(1.0, quality_score))

    async def retry_ocr_with_cloud(self, image_path: str, provider: str = 'google') -> Tuple[str, float]:
        """Retry OCR using cloud provider (placeholder implementation)"""
        # This would integrate with actual cloud OCR APIs
        logger.info(f"Retrying OCR with {provider} for {image_path}")

        # Placeholder implementation
        await asyncio.sleep(0.1)  # Simulate API call

        if provider == 'google':
            # Google Cloud Vision API would go here
            return "High quality OCR text from Google Cloud Vision", 0.95
        elif provider == 'azure':
            # Azure Computer Vision API would go here
            return "High quality OCR text from Azure Computer Vision", 0.93
        elif provider == 'aws':
            # AWS Textract would go here
            return "High quality OCR text from AWS Textract", 0.91

        return "", 0.0

class ContentQualityAnalyzer:
    """Analyzes content quality and classifies content type"""

    def __init__(self):
        self.language_patterns = self._build_language_patterns()
        self.structure_patterns = self._build_structure_patterns()

    def analyze_content_quality(self, content: str, filename: str = None) -> QualityMetrics:
        """Comprehensive content quality analysis"""

        # Basic metrics
        char_count = len(content)
        word_count = len(content.split())
        line_count = len(content.split('\n'))

        # Signal/noise analysis
        signal_ratio = self._calculate_signal_ratio(content)
        noise_ratio = 1.0 - signal_ratio

        # Content type classification
        content_type = self._classify_content_type(content, filename)

        # Language and encoding quality
        language_confidence = self._assess_language_confidence(content)
        encoding_quality = self._assess_encoding_quality(content)

        # Structure analysis
        structure_score = self._assess_structure_quality(content, content_type)

        # Readability assessment
        readability_score = self._calculate_readability(content)

        # Quality indicators
        has_meaningful_content = self._has_meaningful_content(content)
        has_proper_formatting = self._has_proper_formatting(content, content_type)
        has_excessive_repetition = self._has_excessive_repetition(content)
        has_binary_corruption = self._has_binary_corruption(content)
        has_encoding_issues = self._has_encoding_issues(content)

        # Overall quality calculation
        overall_score = self._calculate_overall_quality(
            signal_ratio, readability_score, language_confidence,
            encoding_quality, structure_score, has_meaningful_content
        )

        # Quality level determination
        quality_level = self._determine_quality_level(overall_score, signal_ratio)

        # Recommendations
        recommended_action, processing_notes = self._generate_recommendations(
            overall_score, quality_level, has_binary_corruption,
            has_encoding_issues, signal_ratio
        )

        return QualityMetrics(
            overall_score=overall_score,
            quality_level=quality_level,
            content_type=content_type,
            signal_ratio=signal_ratio,
            noise_ratio=noise_ratio,
            readability_score=readability_score,
            language_confidence=language_confidence,
            encoding_quality=encoding_quality,
            structure_score=structure_score,
            has_meaningful_content=has_meaningful_content,
            has_proper_formatting=has_proper_formatting,
            has_excessive_repetition=has_excessive_repetition,
            has_binary_corruption=has_binary_corruption,
            has_encoding_issues=has_encoding_issues,
            recommended_action=recommended_action,
            processing_notes=processing_notes
        )

    def _calculate_signal_ratio(self, content: str) -> float:
        """Calculate ratio of meaningful content vs noise"""
        if not content:
            return 0.0

        # Count meaningful elements
        words = content.split()
        meaningful_chars = sum(1 for c in content if c.isalnum() or c in ' .,;:!?-()[]{}"\'\n')
        total_chars = len(content)

        # Check for patterns that indicate signal
        has_sentences = bool(re.search(r'[.!?]+\s+[A-Z]', content))
        has_structure = bool(re.search(r'\n\s*[-*•]|\n\d+\.|\n#+\s', content))
        word_variety = len(set(word.lower() for word in words)) / max(len(words), 1)

        # Calculate signal ratio
        char_ratio = meaningful_chars / total_chars
        signal_indicators = [
            char_ratio,
            min(1.0, word_variety * 2),  # Vocabulary diversity
            0.1 if has_sentences else 0.0,  # Sentence structure
            0.1 if has_structure else 0.0,  # Document structure
        ]

        return min(1.0, sum(signal_indicators) / len(signal_indicators))

    def _classify_content_type(self, content: str, filename: str = None) -> ContentType:
        """Classify content type for appropriate processing"""

        # Check file extension hints
        if filename:
            ext = filename.lower().split('.')[-1] if '.' in filename else ''
            if ext in ['py', 'js', 'java', 'cpp', 'c', 'cs', 'php', 'rb', 'go']:
                return ContentType.CODE
            if ext in ['csv', 'tsv', 'xlsx', 'xls']:
                return ContentType.DATA_TABLE

        # Content-based classification
        lines = content.split('\n')

        # Check for code patterns
        code_indicators = [
            r'^\s*(def|function|class|import|from|#include)',
            r'^\s*[\w]+\s*=\s*[\w\[\](){}"\']+',
            r'^\s*if\s+.*:',
            r'^\s*for\s+.*:',
            r'^\s*while\s+.*:'
        ]

        code_matches = sum(1 for line in lines for pattern in code_indicators
                          if re.search(pattern, line))
        if code_matches > len(lines) * 0.1:
            return ContentType.CODE

        # Check for conversation patterns
        conversation_patterns = [
            r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}.*\d{1,2}:\d{2}.*-.*:',  # WhatsApp/chat timestamps
            r'^[A-Z][a-z]+:\s',  # Speaker labels
            r'^\[?\d{1,2}:\d{2}\]?\s*<.*>',  # IRC/Discord format
        ]

        conv_matches = sum(1 for line in lines for pattern in conversation_patterns
                          if re.search(pattern, line))
        if conv_matches > len(lines) * 0.05:
            return ContentType.CONVERSATION

        # Check for table/data patterns
        table_indicators = [
            r'^[^,]*,[^,]*,[^,]*,',  # CSV-like
            r'^\s*\|.*\|.*\|',  # Markdown table
            r'^\s*\t.*\t.*\t',  # Tab-separated
        ]

        table_matches = sum(1 for line in lines for pattern in table_indicators
                           if re.search(pattern, line))
        if table_matches > len(lines) * 0.1:
            return ContentType.DATA_TABLE

        # Check for structured text (headings, lists, etc.)
        structure_patterns = [
            r'^#+\s',  # Markdown headings
            r'^\s*[-*•]\s',  # Bullet lists
            r'^\s*\d+\.\s',  # Numbered lists
            r'^[A-Z][A-Z\s]+:',  # Section headers
        ]

        structure_matches = sum(1 for line in lines for pattern in structure_patterns
                               if re.search(pattern, line))
        if structure_matches > len(lines) * 0.05:
            return ContentType.STRUCTURED_TEXT

        # Check for technical documentation
        tech_indicators = [
            r'\b(API|SDK|HTTP|JSON|XML|SQL|REST|GraphQL)\b',
            r'\b(algorithm|function|method|class|interface)\b',
            r'\b(implementation|configuration|deployment)\b',
        ]

        tech_matches = sum(1 for pattern in tech_indicators
                          if re.search(pattern, content, re.IGNORECASE))
        if tech_matches >= 3:
            return ContentType.TECHNICAL_DOC

        # Check for noise/corruption
        garbage_ratio = sum(1 for c in content if ord(c) > 127 and not c.isalpha()) / len(content)
        if garbage_ratio > 0.1:
            return ContentType.CORRUPTED

        # Default to natural language
        return ContentType.NATURAL_LANGUAGE

    def _assess_language_confidence(self, content: str) -> float:
        """Assess confidence in language detection"""
        # Simple heuristic - in production you'd use langdetect or similar

        # Count alphabetic characters in common languages
        latin_chars = sum(1 for c in content if ord(c) < 256 and c.isalpha())
        total_alpha = sum(1 for c in content if c.isalpha())

        if total_alpha == 0:
            return 0.0

        latin_ratio = latin_chars / total_alpha

        # Check for common English words
        common_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        word_matches = sum(1 for word in common_words if word in content.lower().split())

        confidence = (latin_ratio * 0.7) + (min(1.0, word_matches / 5) * 0.3)
        return confidence

    def _assess_encoding_quality(self, content: str) -> float:
        """Assess text encoding quality"""
        if not content:
            return 0.0

        # Check for encoding issues
        replacement_chars = content.count('\ufffd')  # Unicode replacement character
        null_bytes = content.count('\x00')
        control_chars = sum(1 for c in content if ord(c) < 32 and c not in '\t\n\r')

        total_problematic = replacement_chars + null_bytes + control_chars
        quality = 1.0 - (total_problematic / len(content))

        return max(0.0, quality)

    def _assess_structure_quality(self, content: str, content_type: ContentType) -> float:
        """Assess document structure quality"""
        if not content:
            return 0.0

        lines = content.split('\n')
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

        # Basic structure indicators
        has_paragraphs = len(paragraphs) > 1
        avg_line_length = statistics.mean(len(line) for line in lines) if lines else 0
        line_length_variance = statistics.variance(len(line) for line in lines) if len(lines) > 1 else 0

        # Content-type specific structure assessment
        structure_score = 0.5  # Base score

        if content_type == ContentType.STRUCTURED_TEXT:
            headings = sum(1 for line in lines if re.match(r'^#+\s|^[A-Z][A-Z\s]+:$', line))
            lists = sum(1 for line in lines if re.match(r'^\s*[-*•]\s|^\s*\d+\.\s', line))
            structure_score += min(0.3, headings / len(lines) * 5)
            structure_score += min(0.2, lists / len(lines) * 10)

        elif content_type == ContentType.NATURAL_LANGUAGE:
            # Check for proper sentence structure
            sentences = re.split(r'[.!?]+', content)
            avg_sentence_length = statistics.mean(len(s.split()) for s in sentences if s.strip())
            if 5 <= avg_sentence_length <= 25:  # Reasonable sentence length
                structure_score += 0.3

        elif content_type == ContentType.CODE:
            # Check for proper indentation and structure
            indented_lines = sum(1 for line in lines if line.startswith((' ', '\t')))
            if indented_lines > len(lines) * 0.2:
                structure_score += 0.3

        # General quality indicators
        if has_paragraphs:
            structure_score += 0.1
        if 20 <= avg_line_length <= 80:  # Reasonable line length
            structure_score += 0.1

        return min(1.0, structure_score)

    def _calculate_readability(self, content: str) -> float:
        """Calculate content readability score"""
        if not content:
            return 0.0

        sentences = re.split(r'[.!?]+', content)
        words = content.split()

        if not sentences or not words:
            return 0.0

        # Simple readability metrics
        avg_sentence_length = len(words) / len([s for s in sentences if s.strip()])
        avg_word_length = statistics.mean(len(word) for word in words)

        # Flesch-like readability (simplified)
        readability = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_word_length / 6.0)

        # Normalize to 0-1 scale
        return max(0.0, min(1.0, readability / 100.0))

    def _has_meaningful_content(self, content: str) -> bool:
        """Check if content has meaningful information"""
        if not content or len(content.strip()) < 20:
            return False

        words = content.split()
        unique_words = set(word.lower() for word in words)

        # Check vocabulary diversity
        diversity = len(unique_words) / len(words) if words else 0

        # Check for sentence structure
        has_sentences = bool(re.search(r'[.!?]+\s*[A-Z]', content))

        # Check for non-repetitive content
        most_common_word = Counter(words).most_common(1)
        if most_common_word:
            repetition_ratio = most_common_word[0][1] / len(words)
        else:
            repetition_ratio = 0

        return (diversity > 0.3 and has_sentences and repetition_ratio < 0.5)

    def _has_proper_formatting(self, content: str, content_type: ContentType) -> bool:
        """Check if content has proper formatting for its type"""
        if content_type == ContentType.CONVERSATION:
            return bool(re.search(r'\d{1,2}:\d{2}.*-.*:', content))
        elif content_type == ContentType.CODE:
            return bool(re.search(r'^\s+', content, re.MULTILINE))
        elif content_type == ContentType.STRUCTURED_TEXT:
            return bool(re.search(r'^#+\s|^\s*[-*•]\s|^\s*\d+\.\s', content, re.MULTILINE))

        return True  # Default to true for natural language

    def _has_excessive_repetition(self, content: str) -> bool:
        """Check for excessive repetition in content"""
        words = content.split()
        if len(words) < 10:
            return False

        # Check for repeated phrases
        trigrams = [' '.join(words[i:i+3]) for i in range(len(words)-2)]
        trigram_counts = Counter(trigrams)
        most_common_trigram = trigram_counts.most_common(1)

        if most_common_trigram and most_common_trigram[0][1] > len(words) * 0.1:
            return True

        # Check for repeated lines
        lines = content.split('\n')
        line_counts = Counter(line.strip() for line in lines if line.strip())
        most_common_line = line_counts.most_common(1)

        if most_common_line and most_common_line[0][1] > len(lines) * 0.3:
            return True

        return False

    def _has_binary_corruption(self, content: str) -> bool:
        """Check for binary corruption in text"""
        if not content:
            return False

        # Check for high ratio of non-printable characters
        non_printable = sum(1 for c in content if ord(c) < 32 and c not in '\t\n\r')
        high_unicode = sum(1 for c in content if ord(c) > 1000)

        corruption_ratio = (non_printable + high_unicode) / len(content)
        return corruption_ratio > 0.05

    def _has_encoding_issues(self, content: str) -> bool:
        """Check for encoding issues"""
        # Check for replacement characters and encoding artifacts
        issues = [
            content.count('\ufffd') > 0,  # Unicode replacement characters
            '�' in content,  # Question mark in diamond
            content.count('\x00') > 0,  # Null bytes
            re.search(r'[^\x00-\x7F]{20,}', content) is not None,  # Long non-ASCII sequences
        ]

        return any(issues)

    def _calculate_overall_quality(self, signal_ratio: float, readability: float,
                                 language_confidence: float, encoding_quality: float,
                                 structure_score: float, has_meaningful: bool) -> float:
        """Calculate overall quality score"""

        # Weighted combination of quality factors
        weights = [
            (signal_ratio, 0.3),
            (encoding_quality, 0.2),
            (language_confidence, 0.15),
            (structure_score, 0.15),
            (readability, 0.1),
            (1.0 if has_meaningful else 0.0, 0.1)
        ]

        weighted_sum = sum(score * weight for score, weight in weights)
        return min(1.0, max(0.0, weighted_sum))

    def _determine_quality_level(self, overall_score: float, signal_ratio: float) -> QualityLevel:
        """Determine quality level based on scores"""

        if overall_score >= 0.8 and signal_ratio >= 0.8:
            return QualityLevel.EXCELLENT
        elif overall_score >= 0.7 and signal_ratio >= 0.7:
            return QualityLevel.GOOD
        elif overall_score >= 0.5 and signal_ratio >= 0.5:
            return QualityLevel.ACCEPTABLE
        elif overall_score >= 0.3:
            return QualityLevel.POOR
        else:
            return QualityLevel.REJECT

    def _generate_recommendations(self, overall_score: float, quality_level: QualityLevel,
                                has_corruption: bool, has_encoding_issues: bool,
                                signal_ratio: float) -> Tuple[str, List[str]]:
        """Generate processing recommendations"""

        notes = []

        if quality_level == QualityLevel.REJECT:
            return "reject", ["Content quality too low for processing"]

        if has_corruption:
            notes.append("Binary corruption detected - may need manual review")
            return "enhance", notes

        if has_encoding_issues:
            notes.append("Encoding issues detected - content may need cleaning")

        if signal_ratio < 0.5:
            notes.append("Low signal-to-noise ratio - may need preprocessing")

        if overall_score < 0.6:
            notes.append("Quality issues detected - recommend manual review")
            return "enhance", notes

        return "process", notes

    def _build_language_patterns(self) -> Dict[str, List[str]]:
        """Build language detection patterns"""
        return {
            'english': ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to'],
            'spanish': ['el', 'la', 'y', 'o', 'en', 'de', 'a', 'por'],
            'french': ['le', 'la', 'et', 'ou', 'dans', 'de', 'à', 'pour'],
            'german': ['der', 'die', 'das', 'und', 'oder', 'in', 'auf', 'für'],
        }

    def _build_structure_patterns(self) -> Dict[str, str]:
        """Build structure detection patterns"""
        return {
            'heading': r'^#+\s|^[A-Z][A-Z\s]+:$',
            'list': r'^\s*[-*•]\s|^\s*\d+\.\s',
            'code_block': r'^```|^\s{4,}',
            'table': r'^\s*\|.*\|',
            'quote': r'^>\s',
        }

class SemanticTagSimilarity:
    """Detects similar tags using semantic similarity"""

    def __init__(self):
        self.similarity_threshold = 0.8
        self.tag_embeddings = {}  # Cache for tag embeddings

    async def find_similar_tags(self, new_tags: List[str], existing_tags: List[str]) -> Dict[str, List[str]]:
        """Find semantically similar tags"""

        similar_groups = {}

        for new_tag in new_tags:
            similar_groups[new_tag] = []

            # Simple similarity check (in production, use embeddings)
            for existing_tag in existing_tags:
                similarity = self._calculate_tag_similarity(new_tag, existing_tag)
                if similarity > self.similarity_threshold:
                    similar_groups[new_tag].append(existing_tag)

        return similar_groups

    def _calculate_tag_similarity(self, tag1: str, tag2: str) -> float:
        """Calculate semantic similarity between tags"""

        # Normalize tags
        t1 = tag1.lower().strip()
        t2 = tag2.lower().strip()

        # Exact match
        if t1 == t2:
            return 1.0

        # Simple string similarity measures
        # Jaccard similarity on character n-grams
        def get_ngrams(s: str, n: int = 2) -> set:
            return set(s[i:i+n] for i in range(len(s)-n+1))

        ngrams1 = get_ngrams(t1)
        ngrams2 = get_ngrams(t2)

        if not ngrams1 and not ngrams2:
            return 1.0
        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = len(ngrams1.intersection(ngrams2))
        union = len(ngrams1.union(ngrams2))

        jaccard = intersection / union if union > 0 else 0.0

        # Check for substring relationships
        substring_bonus = 0.0
        if t1 in t2 or t2 in t1:
            substring_bonus = 0.3

        # Check for common prefixes/suffixes
        prefix_suffix_bonus = 0.0
        if t1.startswith(t2[:3]) or t2.startswith(t1[:3]):
            prefix_suffix_bonus = 0.1
        if t1.endswith(t2[-3:]) or t2.endswith(t1[-3:]):
            prefix_suffix_bonus += 0.1

        total_similarity = jaccard + substring_bonus + prefix_suffix_bonus
        return min(1.0, total_similarity)

class DocumentQualityTriage:
    """Main triage system orchestrating all quality checks"""

    def __init__(self):
        self.validator = ContentValidator()
        self.quality_analyzer = ContentQualityAnalyzer()
        self.ocr_assessment = OCRQualityAssessment()
        self.tag_similarity = SemanticTagSimilarity()

    async def triage_document(self, content: str, filename: str = None,
                            existing_tags: List[str] = None,
                            ocr_confidence: float = None) -> Dict[str, Any]:
        """Complete document triage and quality assessment"""

        # Step 1: Input validation and cleaning
        validation_result = self.validator.validate_and_clean(content, filename)

        if not validation_result.is_valid:
            return {
                'status': 'rejected',
                'reason': 'validation_failed',
                'validation_result': validation_result.__dict__,
                'recommendation': 'Fix validation errors before processing'
            }

        cleaned_content = validation_result.cleaned_content

        # Step 2: Content quality analysis
        quality_metrics = self.quality_analyzer.analyze_content_quality(cleaned_content, filename)

        # Step 3: OCR quality assessment if applicable
        ocr_needs_retry = False
        if ocr_confidence is not None:
            ocr_quality, needs_retry = self.ocr_assessment.assess_ocr_quality(
                cleaned_content, {'avg_confidence': ocr_confidence * 100}
            )
            quality_metrics.ocr_confidence = ocr_quality
            quality_metrics.requires_ocr_retry = needs_retry
            ocr_needs_retry = needs_retry

        # Step 4: Tag similarity analysis
        tag_similarities = {}
        if existing_tags:
            # Extract potential tags from content for similarity check
            potential_tags = self._extract_potential_tags(cleaned_content)
            tag_similarities = await self.tag_similarity.find_similar_tags(
                potential_tags, existing_tags
            )

        # Step 5: Final recommendation
        final_status, final_recommendation = self._make_final_recommendation(
            quality_metrics, validation_result, ocr_needs_retry
        )

        return {
            'status': final_status,
            'cleaned_content': cleaned_content,
            'quality_metrics': quality_metrics.__dict__,
            'validation_result': validation_result.__dict__,
            'tag_similarities': tag_similarities,
            'recommendation': final_recommendation,
            'processing_pipeline': self._suggest_processing_pipeline(quality_metrics),
            'estimated_processing_time': self._estimate_processing_time(quality_metrics),
            'quality_score': quality_metrics.overall_score
        }

    def _extract_potential_tags(self, content: str) -> List[str]:
        """Extract potential tags from content"""
        # Simple keyword extraction - in production use more sophisticated methods
        words = re.findall(r'\b[A-Za-z]{3,}\b', content.lower())
        word_freq = Counter(words)

        # Get most frequent meaningful words
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'this', 'that', 'are', 'was', 'were', 'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should'}

        potential_tags = [word for word, freq in word_freq.most_common(20)
                         if word not in stop_words and freq > 1]

        return potential_tags[:10]

    def _make_final_recommendation(self, quality_metrics: QualityMetrics,
                                 validation_result: ValidationResult,
                                 ocr_needs_retry: bool) -> Tuple[str, str]:
        """Make final processing recommendation"""

        if quality_metrics.quality_level == QualityLevel.REJECT:
            return 'rejected', 'Document quality too low for processing'

        if validation_result.security_flags:
            return 'rejected', 'Security concerns detected'

        if ocr_needs_retry:
            return 'retry_ocr', 'OCR quality insufficient, retry with cloud service'

        if quality_metrics.quality_level == QualityLevel.POOR:
            return 'needs_enhancement', 'Document needs preprocessing before ingestion'

        if quality_metrics.quality_level in [QualityLevel.ACCEPTABLE, QualityLevel.GOOD, QualityLevel.EXCELLENT]:
            return 'approved', 'Document ready for processing'

        return 'manual_review', 'Document needs manual review'

    def _suggest_processing_pipeline(self, quality_metrics: QualityMetrics) -> List[str]:
        """Suggest processing pipeline based on quality assessment"""
        pipeline = ['basic_cleaning']

        if quality_metrics.content_type == ContentType.CODE:
            pipeline.append('code_aware_chunking')
        elif quality_metrics.content_type == ContentType.CONVERSATION:
            pipeline.append('conversation_parsing')
        elif quality_metrics.content_type == ContentType.DATA_TABLE:
            pipeline.append('table_structure_parsing')

        if quality_metrics.signal_ratio < 0.7:
            pipeline.append('noise_filtering')

        if quality_metrics.has_encoding_issues:
            pipeline.append('encoding_repair')

        if quality_metrics.structure_score < 0.5:
            pipeline.append('structure_enhancement')

        pipeline.extend(['llm_enrichment', 'vector_embedding', 'storage'])

        return pipeline

    def _estimate_processing_time(self, quality_metrics: QualityMetrics) -> str:
        """Estimate processing time based on quality and content type"""
        base_time = 2.0  # Base processing time in seconds

        # Adjust based on quality
        if quality_metrics.quality_level == QualityLevel.POOR:
            base_time *= 2.0
        elif quality_metrics.quality_level == QualityLevel.EXCELLENT:
            base_time *= 0.8

        # Adjust based on content type
        if quality_metrics.content_type == ContentType.CODE:
            base_time *= 1.5
        elif quality_metrics.content_type == ContentType.CONVERSATION:
            base_time *= 1.3
        elif quality_metrics.content_type == ContentType.DATA_TABLE:
            base_time *= 1.4

        if quality_metrics.requires_ocr_retry:
            base_time += 15.0  # Cloud OCR overhead

        return f"{base_time:.1f} seconds"

# Example usage and testing
async def test_quality_triage():
    """Test the quality triage system"""

    triage = DocumentQualityTriage()

    # Test cases
    test_documents = [
        ("High quality document with proper structure and meaningful content.", "good_doc.txt"),
        ("This is a very short doc", "short.txt"),
        ("ÿþÿþgarbage\x00\x01\x02binary corruption here", "corrupted.txt"),
        ("The the the the repeated words words words everywhere", "repetitive.txt"),
        ("Machine learning algorithms use neural networks for pattern recognition. Deep learning is a subset of machine learning that uses multiple layers.", "ml_article.txt")
    ]

    print("🧪 Document Quality Triage Test Results")
    print("======================================")

    for content, filename in test_documents:
        print(f"\n📄 Testing: {filename}")
        print(f"Content: {content[:50]}...")

        result = await triage.triage_document(content, filename)

        print(f"Status: {result['status']}")
        print(f"Quality Score: {result['quality_score']:.2f}")
        print(f"Content Type: {result['quality_metrics']['content_type']}")
        print(f"Signal Ratio: {result['quality_metrics']['signal_ratio']:.2f}")
        print(f"Recommendation: {result['recommendation']}")

        if result['validation_result']['content_warnings']:
            print(f"⚠️  Warnings: {result['validation_result']['content_warnings']}")

if __name__ == "__main__":
    asyncio.run(test_quality_triage())
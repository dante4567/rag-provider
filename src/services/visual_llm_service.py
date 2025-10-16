"""
Visual LLM Service - Extract text from images using Vision AI via LiteLLM

Automatically falls back to visual LLMs when OCR quality is poor.
Supports: Gemini, GPT-4V, Claude Vision via LiteLLM unified API.
"""

import os
import base64
import logging
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image
import io
import litellm

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

logger = logging.getLogger(__name__)

class VisualLLMService:
    """Extract text from images using Visual LLMs via LiteLLM"""

    def __init__(self):
        # Check for vision model API keys (LiteLLM will handle routing)
        self.has_gemini = bool(os.getenv('GOOGLE_API_KEY'))
        self.has_openai = bool(os.getenv('OPENAI_API_KEY'))
        self.has_anthropic = bool(os.getenv('ANTHROPIC_API_KEY'))

        self.enabled = PDF2IMAGE_AVAILABLE and (self.has_gemini or self.has_openai or self.has_anthropic)

        if self.enabled:
            logger.info(f"✅ Visual LLM Service initialized via LiteLLM (providers: "
                       f"{'Gemini ' if self.has_gemini else ''}"
                       f"{'GPT-4V ' if self.has_openai else ''}"
                       f"{'Claude ' if self.has_anthropic else ''})")
        else:
            reasons = []
            if not PDF2IMAGE_AVAILABLE:
                reasons.append("pdf2image not installed")
            if not any([self.has_gemini, self.has_openai, self.has_anthropic]):
                reasons.append("no vision model API keys set")
            logger.warning(f"⚠️ Visual LLM disabled: {', '.join(reasons)}")

    def is_available(self) -> bool:
        """Check if Visual LLM is available"""
        return self.enabled

    async def extract_from_pdf(
        self,
        pdf_path: str,
        model: str = "gemini-2.0-flash-exp",
        max_pages: int = 10
    ) -> Dict:
        """
        Extract text from PDF using Visual LLM

        Args:
            pdf_path: Path to PDF file
            model: Visual LLM model (default: gemini-2.0-flash-exp)
            max_pages: Maximum pages to process (default: 10)

        Returns:
            Dict with extracted content, metadata, and cost
        """
        if not self.enabled:
            raise RuntimeError("Visual LLM service not available")

        logger.info(f"👁️ Extracting text from {pdf_path} using {model}")

        # Convert PDF to images
        try:
            images = convert_from_path(pdf_path, dpi=200, fmt='png')
            if len(images) > max_pages:
                logger.warning(f"PDF has {len(images)} pages, processing first {max_pages}")
                images = images[:max_pages]
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            raise

        # Process each page
        all_results = []
        total_cost = 0.0

        for i, image in enumerate(images):
            logger.info(f"Processing page {i+1}/{len(images)}")

            try:
                result = await self._analyze_image(image, model, page_num=i+1)
                all_results.append(result)
                total_cost += result.get('cost', 0.0)
            except Exception as e:
                logger.error(f"Failed to analyze page {i+1}: {e}")
                all_results.append({
                    'full_text': f"[Error processing page {i+1}: {str(e)}]",
                    'cost': 0.0
                })

        # Combine results
        combined_text = "\n\n".join([
            f"--- Page {i+1} ---\n{r.get('full_text', '')}"
            for i, r in enumerate(all_results)
        ])

        # Merge metadata from all pages
        all_names = []
        all_dates = []
        all_amounts = []

        for r in all_results:
            key_info = r.get('key_info', {})
            all_names.extend(key_info.get('names', []))
            all_dates.extend(key_info.get('dates', []))
            all_amounts.extend(key_info.get('amounts', []))

        # Get title and summary from first page
        first_page = all_results[0] if all_results else {}

        return {
            'text': combined_text,
            'title': first_page.get('title', 'Scanned Document'),
            'summary': first_page.get('summary', ''),
            'document_type': first_page.get('document_type', 'scanned'),
            'metadata': {
                'extraction_method': 'visual_llm',
                'model': model,
                'pages_processed': len(images),
                'total_cost': total_cost,
                'names': list(set(all_names)),
                'dates': list(set(all_dates)),
                'amounts': list(set(all_amounts))
            },
            'cost': total_cost
        }

    async def _analyze_image(
        self,
        image: Image.Image,
        model: str,
        page_num: int = 1
    ) -> Dict:
        """Analyze single image with Visual LLM via LiteLLM"""

        try:
            # Convert image to base64 for LiteLLM
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

            prompt = f"""Analyze this scanned document image (page {page_num}).

Extract the following information:

1. **Title** - What is this document called?
2. **Summary** - Brief 2-3 sentence summary
3. **Document Type** - (letter, form, receipt, invoice, table, report, etc.)
4. **Key Information**:
   - Names of people or organizations
   - Dates mentioned
   - Amounts, prices, or numbers
   - Action items or important points

5. **Full Text** - Complete transcription of all readable text

Respond in JSON format:
{{
  "title": "...",
  "summary": "...",
  "document_type": "...",
  "key_info": {{
    "names": ["..."],
    "dates": ["..."],
    "amounts": ["..."],
    "action_items": ["..."]
  }},
  "full_text": "..."
}}

If you cannot read something clearly, note it with [unclear].
"""

            # Call LiteLLM with vision support
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": f"data:image/png;base64,{image_base64}"
                        }
                    ]
                }
            ]

            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=0.1
            )

            # Parse JSON response
            import json
            import re

            text = response.choices[0].message.content

            # Look for JSON block (sometimes wrapped in ```json```)
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                text = json_match.group(1)

            try:
                result = json.loads(text)
                result['cost'] = response._hidden_params.get('response_cost', 0.0) or 0.001  # Fallback estimate
                logger.info(f"✅ Vision LLM extracted: {result.get('title', 'Untitled')}")
                return result
            except json.JSONDecodeError:
                # Fallback: use raw text
                logger.warning(f"Could not parse JSON, using raw text")
                return {
                    'title': 'Scanned Document',
                    'summary': text[:200],
                    'document_type': 'scanned',
                    'key_info': {},
                    'full_text': text,
                    'cost': 0.001  # Fallback estimate
                }

        except Exception as e:
            logger.error(f"Gemini Vision error: {e}")
            return {
                'title': 'Error Processing Page',
                'summary': f'Error: {str(e)}',
                'full_text': f'[Error: {str(e)}]',
                'cost': 0.0
            }

    def _calculate_gemini_cost(self, image: Image.Image) -> float:
        """
        Calculate Gemini Vision API cost

        Gemini 2.0 Flash pricing:
        - Images under 128 tokens: Free
        - Images 128+ tokens: $0.000001 per token

        Approximate: $0.0025 per image (conservative estimate)
        """
        return 0.0025

    def assess_ocr_quality(self, text: str) -> Dict:
        """
        Assess OCR quality to determine if Visual LLM should be used

        Returns:
            Dict with quality assessment
        """
        if not text or len(text.strip()) < 10:
            return {
                'quality': 'poor',
                'score': 0.0,
                'use_visual_llm': True,
                'reason': 'Empty or very short text'
            }

        # Common OCR gibberish patterns
        gibberish_patterns = [
            '* = u L',
            '> * A >',
            '+ + u $',
            'EEE',
            'CCR',
            'HHH',
            'AAA',
            '= = u',
            'L L L',
            'CEE CEE'
        ]

        # Count gibberish occurrences
        gibberish_count = sum(text.count(pattern) for pattern in gibberish_patterns)

        # Count total words
        words = text.split()
        word_count = len(words)

        # Calculate gibberish ratio
        gibberish_ratio = min(1.0, gibberish_count / max(word_count, 1))

        # Check for repeated single characters
        import re
        repeated_singles = len(re.findall(r'\b[A-Z]\b', text))
        repeated_ratio = repeated_singles / max(word_count, 1)

        # Overall quality score (0-1, higher is better)
        quality_score = 1.0 - (gibberish_ratio * 0.7 + repeated_ratio * 0.3)

        # Determine quality level
        if quality_score < 0.3:
            quality = 'poor'
            use_visual = True
            reason = f'High gibberish ratio ({gibberish_ratio:.1%})'
        elif quality_score < 0.6:
            quality = 'fair'
            use_visual = False
            reason = f'Moderate quality (score: {quality_score:.2f})'
        else:
            quality = 'good'
            use_visual = False
            reason = f'Good quality (score: {quality_score:.2f})'

        return {
            'quality': quality,
            'score': quality_score,
            'use_visual_llm': use_visual,
            'reason': reason,
            'gibberish_count': gibberish_count,
            'gibberish_ratio': gibberish_ratio
        }

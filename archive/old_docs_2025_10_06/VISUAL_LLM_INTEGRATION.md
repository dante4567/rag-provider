# 👁️ Visual LLM Integration - For Scanned Documents

**Problem**: OCR fails on many scanned documents, producing gibberish
**Examples Found**:
- `Scanned-Document-TELLE-CCR-21m-9-og-le-fl-Aa-A)_060d7353.md`
- `Scanned-Document-with-Unreadable-Content_1d5b6abe.md`

**Solution**: Use Visual LLMs to "see" the document directly

---

## 🎯 The Perfect Use Case

### When to Use Visual LLM:

**Automatically trigger when**:
1. OCR quality score < 0.5 (poor)
2. Gibberish ratio > 50%
3. Document type is scanned/image
4. User explicitly requests it

### Why Visual LLM is Better:

**Traditional OCR**:
- ❌ Fails on complex layouts (tables, forms)
- ❌ Struggles with handwriting
- ❌ Can't understand context
- ❌ Produces gibberish: "* = u L * = u L * = u L"

**Visual LLM** (GPT-4V, Claude 3.5 with vision, Gemini Pro Vision):
- ✅ Sees the whole page as an image
- ✅ Understands structure (tables, lists, forms)
- ✅ Can read handwriting
- ✅ Provides context and summary
- ✅ Extracts key information intelligently

---

## 🤖 Available Visual LLMs

### Option 1: GPT-4 Vision (OpenAI)
**Model**: `gpt-4-vision-preview` or `gpt-4o`
**Cost**: $0.01 per image (1024×1024)
**Pros**:
- Excellent accuracy
- Good with complex documents
- Fast
**Cons**:
- More expensive than OCR
- Rate limits

### Option 2: Claude 3.5 Sonnet with Vision (Anthropic)
**Model**: `claude-3-5-sonnet-20241022`
**Cost**: $3/MTok input (images encoded as tokens)
**Pros**:
- Best quality
- Great with structured documents
- Already in your stack!
**Cons**:
- Most expensive
- Image encoding overhead

### Option 3: Gemini Pro Vision (Google)
**Model**: `gemini-pro-vision` or `gemini-2.0-flash-exp`
**Cost**: $0.0025 per image
**Pros**:
- Cheapest option
- Good quality
- Fast
**Cons**:
- Slightly lower accuracy than GPT-4V

### Recommendation: **Gemini 2.0 Flash** (cheapest + fast)

---

## 🏗️ Implementation Architecture

### Flow Diagram:

```
PDF Upload
    ↓
Extract Text (traditional)
    ↓
OCR Quality Assessment
    ↓
  [Good?] → Yes → Continue with enrichment
    ↓ No (gibberish detected)
    ↓
Convert PDF → Images (per page)
    ↓
Send to Visual LLM (Gemini/GPT-4V)
    ↓
Get structured response
    ↓
Continue with enrichment
```

### Visual LLM Prompt:

```markdown
You are analyzing a scanned document image.

Please extract:
1. **Title** of the document
2. **Summary** (2-3 sentences)
3. **Key Information**:
   - Names mentioned
   - Dates
   - Important numbers/amounts
   - Action items
4. **Document Type** (letter, form, receipt, table, etc.)
5. **Full Text** (transcribe everything you can read)

Format as JSON:
{
  "title": "...",
  "summary": "...",
  "document_type": "...",
  "key_info": {
    "names": ["..."],
    "dates": ["..."],
    "amounts": ["..."],
    "action_items": ["..."]
  },
  "full_text": "..."
}
```

---

## 🔧 Implementation Plan

### Phase 1: Detection & Fallback (4 hours)

**File**: `src/services/document_service.py`

```python
async def extract_text_from_pdf(self, file_path: str) -> str:
    # Try traditional extraction
    text = self._extract_text_pypdf(file_path)

    # Assess quality
    quality = self._assess_ocr_quality(text)

    if quality['ocr_quality'] == 'poor':
        logger.info(f"Poor OCR detected, trying Visual LLM")
        # Fallback to Visual LLM
        text = await self._extract_with_visual_llm(file_path)

    return text
```

### Phase 2: Visual LLM Service (6 hours)

**New File**: `src/services/visual_llm_service.py`

```python
import base64
from pathlib import Path
from pdf2image import convert_from_path
from typing import Dict, List
import google.generativeai as genai

class VisualLLMService:
    """Extract text from images using Visual LLMs"""

    def __init__(self):
        self.gemini_api_key = os.getenv('GOOGLE_API_KEY')
        genai.configure(api_key=self.gemini_api_key)

    async def extract_from_pdf(
        self,
        pdf_path: str,
        model: str = "gemini-2.0-flash-exp"
    ) -> Dict[str, any]:
        """
        Extract text from PDF using Visual LLM

        Args:
            pdf_path: Path to PDF file
            model: Visual LLM model to use

        Returns:
            Dict with extracted content and metadata
        """
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=200)

        all_results = []
        total_cost = 0

        # Process each page
        for i, image in enumerate(images):
            logger.info(f"Processing page {i+1}/{len(images)} with {model}")

            result = await self._analyze_image(image, model)
            all_results.append(result)
            total_cost += result.get('cost', 0)

        # Combine results
        combined_text = "\n\n".join([
            f"--- Page {i+1} ---\n{r['full_text']}"
            for i, r in enumerate(all_results)
        ])

        # Merge metadata
        all_names = []
        all_dates = []
        for r in all_results:
            all_names.extend(r.get('key_info', {}).get('names', []))
            all_dates.extend(r.get('key_info', {}).get('dates', []))

        return {
            'text': combined_text,
            'title': all_results[0].get('title', 'Scanned Document'),
            'summary': all_results[0].get('summary', ''),
            'metadata': {
                'extraction_method': 'visual_llm',
                'model': model,
                'pages': len(images),
                'cost': total_cost,
                'names': list(set(all_names)),
                'dates': list(set(all_dates))
            }
        }

    async def _analyze_image(
        self,
        image,
        model: str
    ) -> Dict:
        """Analyze single image with Visual LLM"""

        # Convert PIL image to base64
        import io
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        # Gemini Vision
        if "gemini" in model:
            return await self._gemini_vision(image, model)

        # GPT-4 Vision
        elif "gpt-4" in model:
            return await self._gpt4_vision(img_base64, model)

        # Claude Vision
        elif "claude" in model:
            return await self._claude_vision(img_base64, model)

    async def _gemini_vision(self, image, model: str) -> Dict:
        """Use Gemini Vision"""
        genai_model = genai.GenerativeModel(model)

        prompt = """
        Analyze this scanned document image.

        Extract:
        1. Title of the document
        2. Brief summary (2-3 sentences)
        3. Document type (letter, form, receipt, table, etc.)
        4. Key information: names, dates, amounts, action items
        5. Full text transcription

        Return as JSON:
        {
          "title": "...",
          "summary": "...",
          "document_type": "...",
          "key_info": {
            "names": [],
            "dates": [],
            "amounts": [],
            "action_items": []
          },
          "full_text": "..."
        }
        """

        response = genai_model.generate_content([prompt, image])

        # Parse JSON response
        import json
        try:
            result = json.loads(response.text)
            result['cost'] = self._calculate_gemini_cost(image)
            return result
        except:
            # Fallback if not JSON
            return {
                'title': 'Scanned Document',
                'summary': response.text[:200],
                'full_text': response.text,
                'cost': self._calculate_gemini_cost(image)
            }

    def _calculate_gemini_cost(self, image) -> float:
        """Calculate Gemini Vision cost"""
        # Gemini 2.0 Flash: $0.0025 per image
        return 0.0025

    async def _gpt4_vision(self, img_base64: str, model: str) -> Dict:
        """Use GPT-4 Vision (implementation similar)"""
        # TODO: Implement OpenAI Vision API
        pass

    async def _claude_vision(self, img_base64: str, model: str) -> Dict:
        """Use Claude Vision (implementation similar)"""
        # TODO: Implement Anthropic Vision API
        pass
```

### Phase 3: Integration (2 hours)

**Update**: `src/services/document_service.py`

```python
from .visual_llm_service import VisualLLMService

class DocumentService:
    def __init__(self):
        self.visual_llm = VisualLLMService()

    async def extract_text(self, file_path: str) -> Dict:
        """Extract text with automatic fallback to Visual LLM"""

        # Try traditional extraction
        text = await self._extract_text_traditional(file_path)

        # Assess quality
        quality = self._assess_text_quality(text)

        if quality['is_gibberish']:
            logger.info(f"⚠️ Poor OCR quality, using Visual LLM")
            # Use Visual LLM
            result = await self.visual_llm.extract_from_pdf(file_path)

            return {
                'text': result['text'],
                'title': result['title'],
                'extraction_method': 'visual_llm',
                'cost': result['metadata']['cost'],
                'metadata': result['metadata']
            }
        else:
            return {
                'text': text,
                'extraction_method': 'traditional',
                'cost': 0.0
            }

    def _assess_text_quality(self, text: str) -> Dict:
        """Quick gibberish detection"""
        words = text.split()
        if len(words) < 10:
            return {'is_gibberish': False}

        # Count nonsense patterns
        gibberish_patterns = [
            '* = u L',
            '> * A >',
            'EEE',
            'CCR',
            '+ + u $'
        ]

        nonsense_count = sum(text.count(p) for p in gibberish_patterns)

        return {
            'is_gibberish': nonsense_count > 5,
            'confidence': min(1.0, nonsense_count / 20)
        }
```

---

## 💰 Cost Analysis

### Current OCR Approach:
- **Tesseract**: Free (but produces gibberish)
- **Enrichment**: $0.0106 (wasted on gibberish)
- **Total per poor-quality doc**: **$0.0106 wasted**

### Visual LLM Approach:

**Option 1: Gemini 2.0 Flash** (Recommended)
- **Per image**: $0.0025
- **2-page doc**: $0.005
- **Enrichment**: $0.0106 (on good content!)
- **Total**: **$0.0156 per doc**
- **Cost increase**: +$0.005 (+47%)

**Option 2: GPT-4 Vision**
- **Per image**: $0.01
- **2-page doc**: $0.02
- **Total**: **$0.0306 per doc**
- **Cost increase**: +$0.02 (+189%)

**Option 3: Claude Vision**
- **Per image**: ~$0.015 (estimated)
- **2-page doc**: $0.03
- **Total**: **$0.0406 per doc**
- **Cost increase**: +$0.03 (+283%)

### ROI Calculation:

**For 10% of docs with poor OCR** (10 out of 100):
- **Current**: 10 × $0.0106 = $0.106 (wasted)
- **With Gemini**: 10 × $0.0156 = $0.156
- **Net cost**: +$0.05 for 100 docs
- **Benefit**: Actually usable content!

**Verdict**: Worth it! $0.05/100 docs for readable content.

---

## 🎯 Implementation Priority

### Quick Win (2 hours):
1. **Add gibberish detection**
2. **Flag poor OCR documents**
3. **Add manual "Retry with Visual LLM" option**

### Full Integration (12 hours):
1. **Implement VisualLLMService** (6h)
2. **Integrate with DocumentService** (2h)
3. **Add automatic fallback** (2h)
4. **Test with 10 scanned docs** (2h)

### Polish (4 hours):
1. **Add UI toggle** (choose OCR vs Visual LLM)
2. **Cost tracking** for visual extractions
3. **Comparison view** (OCR vs Visual side-by-side)

**Total**: 18 hours for full implementation

---

## ✅ Recommended Approach

### This Week (4 hours):

1. **Add Gemini 2.0 Flash integration** (3h)
   - Only for scanned docs with poor OCR
   - Automatic fallback

2. **Test with problem docs** (1h)
   - Re-process the two examples
   - Compare results

### Result:
- ✅ No more gibberish exports
- ✅ Readable content from scans
- ✅ Only +$0.005 per problematic doc
- ✅ Better tag learning (real content)

---

## 📝 Example Output Comparison

### Before (Tesseract OCR):
```markdown
### Content

* = u L * = u L * = u L L = u L * = u L L = u L L
+ + u $ + + u $ + + u $ + + u $ $ + u $ * + u $ *
= = u a = = u a = = u a » = u L L = u L L = u L L L
```

**Tags**: #psychology/adhd, #research/study (meaningless!)
**Cost**: $0.0106 (wasted)

### After (Gemini Vision):
```markdown
### Content

**Document Title**: Medical Appointment Confirmation
**Date**: April 18, 2023
**Patient**: Frau Bannasch
**Appointment**: Tuesday, April 25, 2023 at 2:30 PM
**Doctor**: Dr. Schmidt
**Location**: Medical Center, Room 305

Please bring:
- Insurance card
- Previous medical records
- List of current medications
```

**Tags**: #health/medical, #appointment, #healthcare (accurate!)
**Cost**: $0.0156 (+$0.005)
**Benefit**: Actually useful!

---

## 🚀 Next Steps

**Want me to implement this?**

I can add Gemini Vision integration in ~3 hours:
1. Create `VisualLLMService`
2. Add automatic fallback for poor OCR
3. Re-process the two problem docs
4. Show you the results

**Estimated cost for re-processing 10 poor-OCR docs**: ~$0.05

Let me know if you want to proceed!

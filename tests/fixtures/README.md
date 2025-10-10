# Test Fixtures

This directory contains sample files used for testing document processing.

## Files

- **test_document.txt** - Simple text document
- **test_simple.txt** - Minimal text file
- **test_email.eml** - Email message sample
- **test_ocr_image.png** - Image for OCR testing
- **test_research_paper.pdf** - PDF document sample
- **test_whatsapp_export.txt** - WhatsApp chat export sample
- **whatsapp_sample.txt** - Additional WhatsApp sample

## Usage

These files are used by integration tests to verify:
- Document format parsing (PDF, text, email)
- OCR functionality (images)
- WhatsApp parser
- Text extraction quality

## Adding New Fixtures

When adding new test fixtures:
1. Keep files small (< 100KB)
2. Use anonymized/synthetic data
3. Document the purpose in this README
4. Ensure no sensitive information is included

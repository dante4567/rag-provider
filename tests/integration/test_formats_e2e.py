"""
End-to-end format testing for critical document types

Tests full ingestion pipeline: parse → enrich → chunk → embed → Obsidian export

Critical formats for personal/family use:
- Email (.eml)
- Scanned PDF (with OCR)
- Scanned TIFF (with OCR)
- WhatsApp chat exports
"""
import pytest
import tempfile
from pathlib import Path
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import Image, ImageDraw, ImageFont
import io

from src.services.rag_service import RAGService
from src.core.config import get_settings


@pytest.fixture
def rag_service():
    """Create RAG service for testing"""
    settings = get_settings()
    return RAGService(settings)


class TestEmailFormat:
    """Test email (.eml) ingestion"""

    @pytest.fixture
    def sample_email(self, tmp_path):
        """Create realistic .eml file"""
        msg = MIMEMultipart()
        msg['From'] = "daniel.teckentrup@example.com"
        msg['To'] = "lawyer@example.com"
        msg['Subject'] = "School Enrollment Documents - Urgent"
        msg['Date'] = "2025-10-15 14:30:00"

        body = """
Dear Ms. Schmidt,

Please find attached the enrollment documents for Pola's school application.

We need to complete the following by November 15, 2025:
1. Sign the enrollment contract
2. Submit proof of residence
3. Pay the registration fee (€450)

The school visit is scheduled for November 1, 2025 at 10:00 AM.

Contact: Waldorf School Köln, +49 221 12345678

Best regards,
Daniel Teckentrup
"""
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        email_path = tmp_path / "school-enrollment.eml"
        with open(email_path, 'w', encoding='utf-8') as f:
            f.write(msg.as_string())

        return email_path

    @pytest.mark.asyncio
    async def test_email_full_pipeline(self, rag_service, sample_email):
        """Test email ingestion extracts key information"""
        result = await rag_service.process_file(
            str(sample_email),
            process_ocr=False,
            generate_obsidian=True
        )

        assert result.success
        assert result.metadata is not None

        # Check key extractions
        metadata = result.metadata
        assert "school" in metadata.get('summary', '').lower() or \
               "school" in str(metadata.get('topics', [])).lower()

        # Should extract dates
        dates = metadata.get('entities', {}).get('dates', [])
        assert len(dates) >= 2  # November 15 and November 1

        # Should extract people
        people = metadata.get('people', [])
        assert len(people) >= 2  # Daniel and Ms. Schmidt

        # Should extract phone number
        numbers = metadata.get('entities', {}).get('numbers', [])
        assert any('+49' in str(n) for n in numbers)

        # Obsidian file should exist
        assert result.obsidian_path is not None
        obsidian_file = Path(result.obsidian_path)
        assert obsidian_file.exists()

        # Check Obsidian content
        content = obsidian_file.read_text()
        assert 'people_detailed:' in content
        assert 'dates_detailed:' in content
        assert 'School Enrollment' in content or 'school' in content.lower()


class TestScannedPDFFormat:
    """Test scanned PDF with OCR"""

    @pytest.fixture
    def sample_scanned_pdf(self, tmp_path):
        """Create a simple scanned PDF (image-based)"""
        # Create image with text
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)

        # Try to use a basic font, fallback to default
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            font = ImageFont.load_default()

        text = """
        Amtsgericht Köln
        Aktenzeichen: 310 F 160/24

        Beschluss vom 30.10.2024

        In der Familiensache betreffend:
        - Daniel Teckentrup (Antragsteller)
        - Fanny Teckentrup (Antragsgegnerin)
        - Pola Teckentrup (geb. 20.01.2020)

        Das Gericht entscheidet:
        1. Umgangsregelung gilt ab 31.10.2024
        2. Übergabe erfolgt in der Kita Villa Luna
        3. Nächster Termin: 06.11.2024

        Richterin: Frau Wiemer
        """

        # Draw text on image
        draw.text((50, 50), text, fill='black', font=font)

        # Save as PDF (simplified - would use pdf2image/img2pdf in reality)
        pdf_path = tmp_path / "court-document-scanned.pdf"
        img.save(pdf_path, 'PDF', resolution=100.0)

        return pdf_path

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_scanned_pdf_with_ocr(self, rag_service, sample_scanned_pdf):
        """Test scanned PDF triggers OCR and extracts text"""
        result = await rag_service.process_file(
            str(sample_scanned_pdf),
            process_ocr=True,  # Enable OCR
            generate_obsidian=True
        )

        assert result.success
        metadata = result.metadata

        # OCR should extract key information
        # Note: OCR might not be perfect, so we check for partial matches
        content_lower = str(metadata).lower()

        # Should detect legal document type
        topics = metadata.get('topics', [])
        assert any('legal' in str(t).lower() for t in topics) or \
               'legal' in content_lower

        # Should extract people
        people = metadata.get('people', [])
        assert len(people) >= 2  # Daniel and Fanny

        # Should extract dates
        dates = metadata.get('entities', {}).get('dates', [])
        assert len(dates) >= 1

        # Should extract case number
        numbers = metadata.get('entities', {}).get('numbers', [])
        assert len(numbers) >= 1


class TestScannedTIFFFormat:
    """Test scanned TIFF with OCR"""

    @pytest.fixture
    def sample_scanned_tiff(self, tmp_path):
        """Create a simple scanned TIFF image"""
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            font = ImageFont.load_default()

        text = """
        School Enrollment Form

        Student: Pola Teckentrup
        Date of Birth: 20.01.2020
        Parents: Daniel & Fanny Teckentrup

        School: Waldorf Köln
        Address: Nippes District, Köln

        Enrollment Date: January 2026
        Monthly Fee: €450

        Contact: +49 221 12345678
        Email: info@waldorf-koeln.de

        Application Deadline: 15.11.2025
        """

        draw.text((50, 50), text, fill='black', font=font)

        tiff_path = tmp_path / "school-enrollment-form.tiff"
        img.save(tiff_path, 'TIFF', dpi=(300, 300))

        return tiff_path

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_scanned_tiff_with_ocr(self, rag_service, sample_scanned_tiff):
        """Test TIFF triggers OCR and extracts information"""
        result = await rag_service.process_file(
            str(sample_scanned_tiff),
            process_ocr=True,
            generate_obsidian=True
        )

        assert result.success
        metadata = result.metadata

        # Should extract people
        people = metadata.get('people', [])
        assert len(people) >= 1  # At least Pola or parents

        # Should extract dates
        dates = metadata.get('entities', {}).get('dates', [])
        assert len(dates) >= 1  # Birth date or deadline

        # Should extract school/education topic
        topics = metadata.get('topics', [])
        content_lower = str(metadata).lower()
        assert any('school' in str(t).lower() for t in topics) or \
               'school' in content_lower or 'education' in content_lower

        # Should extract contact info
        numbers = metadata.get('entities', {}).get('numbers', [])
        assert len(numbers) >= 1  # Phone or fee


class TestWhatsAppFormat:
    """Test WhatsApp chat export"""

    @pytest.fixture
    def sample_whatsapp(self, tmp_path):
        """Create realistic WhatsApp export"""
        content = """
15.10.2025, 14:30 - Daniel Teckentrup: Hi, hast du die Kita-Unterlagen schon unterschrieben?
15.10.2025, 14:35 - Fanny Teckentrup: Ja, habe ich heute morgen gemacht. Wann gibst du sie ab?
15.10.2025, 14:40 - Daniel Teckentrup: Kann ich morgen machen. Übrigens, Lisa Schmidt (unsere Anwältin) hat angerufen.
15.10.2025, 14:42 - Fanny Teckentrup: Was hat sie gesagt?
15.10.2025, 14:45 - Daniel Teckentrup: Der Gerichtstermin ist am 06.11.2024 um 10 Uhr im Amtsgericht Köln.
15.10.2025, 14:50 - Fanny Teckentrup: Ok, ich trage es in den Kalender ein. Brauchst du die Unterlagen vom letzten Mal?
15.10.2025, 14:55 - Daniel Teckentrup: Ja bitte. Die liegen bei dir oder?
15.10.2025, 15:00 - Fanny Teckentrup: Ja, bei mir im Ordner. Hole ich morgen raus.
15.10.2025, 15:05 - Daniel Teckentrup: Super, danke! Dann bringe ich alles zusammen zum Anwalt.
15.10.2025, 15:10 - Fanny Teckentrup: 👍
"""
        whatsapp_path = tmp_path / "family-chat-export.txt"
        whatsapp_path.write_text(content, encoding='utf-8')

        return whatsapp_path

    @pytest.mark.asyncio
    async def test_whatsapp_full_pipeline(self, rag_service, sample_whatsapp):
        """Test WhatsApp chat extraction and threading"""
        result = await rag_service.process_file(
            str(sample_whatsapp),
            process_ocr=False,
            generate_obsidian=True
        )

        assert result.success
        metadata = result.metadata

        # Should extract participants
        people = metadata.get('people', [])
        assert len(people) >= 2  # Daniel and Fanny
        people_str = ' '.join(people)
        assert 'Daniel' in people_str or 'Fanny' in people_str

        # Should extract mentioned person (lawyer)
        assert any('Lisa' in str(p) or 'Schmidt' in str(p) for p in people)

        # Should extract dates
        dates = metadata.get('entities', {}).get('dates', [])
        assert len(dates) >= 1  # Court date

        # Should detect legal topic
        topics = metadata.get('topics', [])
        content_lower = str(metadata).lower()
        assert any('legal' in str(t).lower() for t in topics) or \
               'court' in content_lower or 'legal' in content_lower

        # Obsidian export should exist
        assert result.obsidian_path is not None
        obsidian_file = Path(result.obsidian_path)
        assert obsidian_file.exists()

        # Should have conversation format
        content = obsidian_file.read_text()
        assert 'people_detailed:' in content
        assert len(content) > 200  # Non-trivial content


class TestMixedFormats:
    """Test handling multiple formats in sequence"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sequential_format_processing(self, rag_service, tmp_path):
        """Test processing multiple formats maintains data integrity"""
        # Create simple test files
        formats_to_test = []

        # 1. Text file
        txt_path = tmp_path / "notes.txt"
        txt_path.write_text("Family meeting on 2025-11-15. Daniel and Fanny attending.")
        formats_to_test.append(txt_path)

        # 2. Markdown file
        md_path = tmp_path / "notes.md"
        md_path.write_text("# School Notes\n\nPola's enrollment: contact Lisa Schmidt at +49 221 9999999")
        formats_to_test.append(md_path)

        # 3. Email
        msg = MIMEText("Court date: 06.11.2024 at Amtsgericht Köln", 'plain', 'utf-8')
        msg['From'] = "lawyer@example.com"
        msg['To'] = "daniel@example.com"
        msg['Subject'] = "Court Reminder"
        email_path = tmp_path / "reminder.eml"
        email_path.write_text(msg.as_string())
        formats_to_test.append(email_path)

        # Process all formats
        results = []
        for file_path in formats_to_test:
            result = await rag_service.process_file(
                str(file_path),
                process_ocr=False,
                generate_obsidian=True
            )
            results.append(result)

        # All should succeed
        assert all(r.success for r in results)

        # All should have metadata
        assert all(r.metadata is not None for r in results)

        # All should have Obsidian exports
        assert all(r.obsidian_path is not None for r in results)

        # Check entity extraction across files
        all_people = []
        all_dates = []

        for result in results:
            people = result.metadata.get('people', [])
            dates = result.metadata.get('entities', {}).get('dates', [])
            all_people.extend(people)
            all_dates.extend(dates)

        # Should have extracted people across files
        assert len(all_people) >= 2  # Daniel, Fanny, Lisa

        # Should have extracted dates across files
        assert len(all_dates) >= 2  # Meeting date, court date


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

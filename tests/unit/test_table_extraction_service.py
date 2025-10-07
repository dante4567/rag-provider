"""
Unit tests for TableExtractionService

Tests table extraction from PDFs and CSV sidecar generation
"""
import pytest
from pathlib import Path
import tempfile
import shutil
import csv

from src.services.table_extraction_service import TableExtractionService


class TestTableExtractionService:
    """Test the TableExtractionService class"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def service(self, temp_dir):
        """Create TableExtractionService instance"""
        return TableExtractionService(output_dir=temp_dir)

    def test_init_creates_output_dir(self, temp_dir):
        """Test initialization creates output directory"""
        service = TableExtractionService(output_dir=temp_dir)
        assert service.output_dir.exists()
        assert service.output_dir.is_dir()

    def test_parse_table_text_tab_separated(self, service):
        """Test parsing tab-separated table text"""
        table_text = "Name\tAge\tCity\nAlice\t30\tBerlin\nBob\t25\tMunich"
        rows = service._parse_table_text(table_text)

        assert len(rows) == 3
        assert rows[0] == ["Name", "Age", "City"]
        assert rows[1] == ["Alice", "30", "Berlin"]
        assert rows[2] == ["Bob", "25", "Munich"]

    def test_parse_table_text_pipe_separated(self, service):
        """Test parsing pipe-separated table text"""
        table_text = "Name | Age | City\nAlice | 30 | Berlin"
        rows = service._parse_table_text(table_text)

        assert len(rows) >= 1
        assert "Name" in rows[0]

    def test_parse_table_text_space_separated(self, service):
        """Test parsing space-separated table text"""
        table_text = "Name    Age    City\nAlice   30     Berlin"
        rows = service._parse_table_text(table_text)

        assert len(rows) >= 1
        assert len(rows[0]) >= 2

    def test_save_table_as_csv(self, service):
        """Test saving table data as CSV"""
        table_data = [
            ["Name", "Age"],
            ["Alice", "30"],
            ["Bob", "25"]
        ]

        csv_path = service.save_table_as_csv(
            table_id="table_1",
            table_data=table_data,
            base_filename="test_doc"
        )

        # Check file exists
        assert csv_path.exists()
        assert csv_path.suffix == ".csv"
        assert "test_doc_table_1" in csv_path.name

        # Check CSV content
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) == 3
        assert rows[0] == ["Name", "Age"]
        assert rows[1] == ["Alice", "30"]
        assert rows[2] == ["Bob", "25"]

    def test_save_table_with_unicode(self, service):
        """Test saving table with unicode characters"""
        table_data = [
            ["Name", "City"],
            ["Müller", "München"],
            ["François", "Paris"]
        ]

        csv_path = service.save_table_as_csv(
            table_id="table_1",
            table_data=table_data,
            base_filename="test"
        )

        # Check unicode is preserved
        with open(csv_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert "Müller" in content
        assert "München" in content
        assert "François" in content

    def test_generate_table_references_markdown(self, service):
        """Test markdown generation for table references"""
        csv_files = {
            "table_1": Path("/path/to/doc_table_1.csv"),
            "table_2": Path("/path/to/doc_table_2.csv")
        }

        markdown = service.generate_table_references_markdown(csv_files)

        # Check markdown structure
        assert "## Extracted Tables" in markdown
        assert "table_1" in markdown
        assert "table_2" in markdown
        assert "doc_table_1.csv" in markdown
        assert "doc_table_2.csv" in markdown

    def test_generate_table_references_empty(self, service):
        """Test markdown generation with no tables"""
        markdown = service.generate_table_references_markdown({})
        assert markdown == ""

    def test_extract_tables_from_missing_pdf(self, service, temp_dir):
        """Test table extraction from non-existent PDF"""
        fake_pdf = Path(temp_dir) / "nonexistent.pdf"
        tables = service.extract_tables_from_pdf(fake_pdf)

        # Should handle gracefully and return empty list
        assert tables == []

    def test_save_multiple_tables(self, service):
        """Test saving multiple tables from same document"""
        table1_data = [["A", "B"], ["1", "2"]]
        table2_data = [["X", "Y"], ["9", "10"]]

        csv1 = service.save_table_as_csv("table_1", table1_data, "doc")
        csv2 = service.save_table_as_csv("table_2", table2_data, "doc")

        assert csv1.exists()
        assert csv2.exists()
        assert csv1 != csv2
        assert "doc_table_1" in csv1.name
        assert "doc_table_2" in csv2.name

"""
Table Extraction Service

Extracts tables from PDFs and saves them as CSV sidecars.
Blueprint requirement: Per-document-type table extraction.
"""

import logging
from pathlib import Path
from typing import List, Dict, Tuple
import csv
import io

logger = logging.getLogger(__name__)


class TableExtractionService:
    """Extract and save tables from documents as CSV sidecars"""

    def __init__(self, output_dir: str = "./data/tables"):
        """
        Initialize table extraction service

        Args:
            output_dir: Directory to save extracted CSV files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_tables_from_pdf(
        self,
        pdf_path: Path,
        min_rows: int = 2,
        min_cols: int = 2
    ) -> List[Tuple[str, List[List[str]]]]:
        """
        Extract tables from PDF using unstructured library

        Args:
            pdf_path: Path to PDF file
            min_rows: Minimum rows to consider as table
            min_cols: Minimum columns to consider as table

        Returns:
            List of (table_id, table_data) tuples
        """
        try:
            from unstructured.partition.pdf import partition_pdf
            from unstructured.documents.elements import Table

            logger.info(f"Extracting tables from PDF: {pdf_path.name}")

            # Partition PDF to extract elements
            elements = partition_pdf(str(pdf_path))

            # Filter table elements
            tables = []
            for idx, element in enumerate(elements):
                if isinstance(element, Table):
                    # Parse table text into rows
                    table_text = element.text
                    rows = self._parse_table_text(table_text)

                    # Filter by minimum dimensions
                    if len(rows) >= min_rows and all(len(row) >= min_cols for row in rows if row):
                        table_id = f"table_{idx + 1}"
                        tables.append((table_id, rows))
                        logger.info(f"Found table: {table_id} ({len(rows)} rows)")

            logger.info(f"Extracted {len(tables)} tables from {pdf_path.name}")
            return tables

        except ImportError:
            logger.warning("unstructured library not available for table extraction")
            return []
        except Exception as e:
            logger.error(f"Table extraction failed for {pdf_path}: {e}")
            return []

    def _parse_table_text(self, table_text: str) -> List[List[str]]:
        """
        Parse table text into rows and columns

        Args:
            table_text: Raw table text from unstructured

        Returns:
            List of rows, each row is a list of cell values
        """
        # Split by newlines for rows
        lines = table_text.strip().split('\n')
        rows = []

        for line in lines:
            # Try to detect column separators (tabs, multiple spaces, |)
            if '\t' in line:
                cells = [cell.strip() for cell in line.split('\t')]
            elif '|' in line:
                cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            else:
                # Split on multiple spaces (2+)
                import re
                cells = [cell.strip() for cell in re.split(r'\s{2,}', line) if cell.strip()]

            if cells:  # Only add non-empty rows
                rows.append(cells)

        return rows

    def save_table_as_csv(
        self,
        table_id: str,
        table_data: List[List[str]],
        base_filename: str
    ) -> Path:
        """
        Save table data as CSV sidecar file

        Args:
            table_id: Table identifier (e.g., "table_1")
            table_data: Table rows and columns
            base_filename: Base filename (without extension)

        Returns:
            Path to created CSV file
        """
        csv_filename = f"{base_filename}_{table_id}.csv"
        csv_path = self.output_dir / csv_filename

        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(table_data)

            logger.info(f"Saved table to CSV: {csv_path}")
            return csv_path

        except Exception as e:
            logger.error(f"Failed to save CSV {csv_path}: {e}")
            raise

    def process_pdf_tables(
        self,
        pdf_path: Path,
        base_filename: str = None
    ) -> Dict[str, Path]:
        """
        Extract all tables from PDF and save as CSV sidecars

        Args:
            pdf_path: Path to PDF file
            base_filename: Base filename for CSVs (defaults to PDF stem)

        Returns:
            Dict mapping table_id to CSV path
        """
        if base_filename is None:
            base_filename = pdf_path.stem

        # Extract tables
        tables = self.extract_tables_from_pdf(pdf_path)

        # Save each table as CSV
        csv_files = {}
        for table_id, table_data in tables:
            csv_path = self.save_table_as_csv(table_id, table_data, base_filename)
            csv_files[table_id] = csv_path

        return csv_files

    def generate_table_references_markdown(
        self,
        csv_files: Dict[str, Path]
    ) -> str:
        """
        Generate markdown text referencing extracted tables

        Args:
            csv_files: Dict mapping table_id to CSV path

        Returns:
            Markdown text with table references
        """
        if not csv_files:
            return ""

        lines = ["## Extracted Tables\n"]
        for table_id, csv_path in csv_files.items():
            lines.append(f"- **{table_id}**: `{csv_path.name}`")

        lines.append("")
        return "\n".join(lines)


# Test
if __name__ == "__main__":
    import tempfile

    service = TableExtractionService(output_dir="./test_tables")

    # Create test table data
    test_data = [
        ["Name", "Age", "City"],
        ["Alice", "30", "Berlin"],
        ["Bob", "25", "Munich"]
    ]

    # Save test table
    csv_path = service.save_table_as_csv(
        table_id="table_1",
        table_data=test_data,
        base_filename="test_doc"
    )

    print(f"✅ Created test CSV: {csv_path}")
    print(f"📄 Content: {csv_path.read_text()[:200]}")

    # Generate markdown
    markdown = service.generate_table_references_markdown({"table_1": csv_path})
    print(f"\n📝 Markdown:\n{markdown}")

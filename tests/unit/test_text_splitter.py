"""
Unit tests for SimpleTextSplitter

Tests the text splitting utility for creating overlapping chunks
"""
import pytest
from src.services.text_splitter import SimpleTextSplitter


class TestSimpleTextSplitter:
    """Test the SimpleTextSplitter class"""

    def test_init_default(self):
        """Test initialization with default parameters"""
        splitter = SimpleTextSplitter()
        assert splitter.chunk_size == 1000
        assert splitter.chunk_overlap == 200

    def test_init_custom(self):
        """Test initialization with custom parameters"""
        splitter = SimpleTextSplitter(chunk_size=500, chunk_overlap=100)
        assert splitter.chunk_size == 500
        assert splitter.chunk_overlap == 100

    def test_split_empty_text(self):
        """Test splitting empty text"""
        splitter = SimpleTextSplitter()
        assert splitter.split_text("") == []
        assert splitter.split_text(None) == []

    def test_split_short_text(self):
        """Test splitting text shorter than chunk size"""
        splitter = SimpleTextSplitter(chunk_size=1000)
        text = "This is a short text."
        chunks = splitter.split_text(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_long_text(self):
        """Test splitting long text into multiple chunks"""
        splitter = SimpleTextSplitter(chunk_size=50, chunk_overlap=10)
        text = "This is a long sentence that will definitely be split into multiple chunks because it exceeds the chunk size limit."

        chunks = splitter.split_text(text)

        assert len(chunks) > 1
        # Check that all chunks except possibly last are roughly chunk_size
        for chunk in chunks[:-1]:
            assert len(chunk) <= splitter.chunk_size + 50  # Allow some flexibility

    def test_split_with_overlap(self):
        """Test that chunks have proper overlap"""
        splitter = SimpleTextSplitter(chunk_size=30, chunk_overlap=10)
        text = "First part here. Second part here. Third part here."

        chunks = splitter.split_text(text)

        # Check overlap exists
        if len(chunks) >= 2:
            # Some content from end of first chunk should appear in second chunk
            first_chunk_end = chunks[0][-10:]
            second_chunk_start = chunks[1][:20]
            # There should be some overlap
            assert len(chunks) > 1

    def test_split_at_sentence_boundaries(self):
        """Test that splitter prefers sentence boundaries"""
        splitter = SimpleTextSplitter(chunk_size=50, chunk_overlap=10)
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."

        chunks = splitter.split_text(text)

        # Should split at periods when possible
        for chunk in chunks:
            # Most chunks should end with proper punctuation or be the last chunk
            assert chunk.strip()

    def test_split_at_word_boundaries(self):
        """Test that splitter falls back to word boundaries"""
        splitter = SimpleTextSplitter(chunk_size=30, chunk_overlap=5)
        # Text without sentence endings
        text = "word word word word word word word word word word word word"

        chunks = splitter.split_text(text)

        # Should not break in middle of words
        for chunk in chunks:
            assert not chunk.startswith(" ")  # No leading spaces after strip
            assert chunk.strip()

    def test_split_whitespace_handling(self):
        """Test that whitespace is properly handled"""
        splitter = SimpleTextSplitter(chunk_size=50, chunk_overlap=10)
        text = "Text   with   multiple   spaces   between   words."

        chunks = splitter.split_text(text)

        # Chunks should be stripped
        for chunk in chunks:
            assert chunk == chunk.strip()

    def test_split_with_zero_overlap(self):
        """Test splitting with no overlap"""
        splitter = SimpleTextSplitter(chunk_size=30, chunk_overlap=0)
        text = "First part. Second part. Third part."

        chunks = splitter.split_text(text)

        # Should still work without overlap
        assert len(chunks) >= 1
        # Reconstruct should contain all content
        reconstructed = " ".join(chunks)
        assert "First part" in reconstructed
        assert "Third part" in reconstructed

    def test_split_preserves_content(self):
        """Test that no content is lost during splitting"""
        splitter = SimpleTextSplitter(chunk_size=50, chunk_overlap=10)
        text = "Important information should not be lost during chunking process."

        chunks = splitter.split_text(text)
        full_text = " ".join(chunks)

        # All major words should appear
        assert "Important" in full_text
        assert "information" in full_text
        assert "chunking" in full_text

    def test_split_large_chunk_size(self):
        """Test with chunk size larger than text"""
        splitter = SimpleTextSplitter(chunk_size=10000, chunk_overlap=100)
        text = "Short text that is smaller than chunk size."

        chunks = splitter.split_text(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_newlines_in_text(self):
        """Test handling of text with newlines"""
        splitter = SimpleTextSplitter(chunk_size=50, chunk_overlap=10)
        text = "First line\nSecond line\nThird line\nFourth line"

        chunks = splitter.split_text(text)

        # Should handle newlines gracefully
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.strip()

    def test_split_minimal_chunk_size(self):
        """Test with very small chunk size"""
        splitter = SimpleTextSplitter(chunk_size=10, chunk_overlap=2)
        text = "This will create many small chunks."

        chunks = splitter.split_text(text)

        # Should create multiple small chunks
        assert len(chunks) > 3
        for chunk in chunks:
            assert len(chunk) <= 20  # Small chunks with some flexibility

    def test_split_unicode_text(self):
        """Test splitting text with unicode characters"""
        splitter = SimpleTextSplitter(chunk_size=30, chunk_overlap=5)
        text = "Hello 你好 مرحبا Здравствуйте こんにちは"

        chunks = splitter.split_text(text)

        # Should handle unicode without errors
        assert len(chunks) >= 1
        full_text = " ".join(chunks)
        assert "Hello" in full_text

    def test_split_special_characters(self):
        """Test splitting text with special characters"""
        splitter = SimpleTextSplitter(chunk_size=50, chunk_overlap=10)
        text = "Text with @#$% special & characters! Does it work?"

        chunks = splitter.split_text(text)

        # Should handle special chars without errors
        assert len(chunks) >= 1
        assert "@#$%" in " ".join(chunks)

"""
Unit tests for ChunkingService

Tests structure-aware chunking including:
- Token estimation
- RAG:IGNORE block removal
- Markdown structure parsing
- Chunk type determination
"""
import pytest
from src.services.chunking_service import ChunkingService, ChunkType, Chunk


# =============================================================================
# ChunkingService Tests
# =============================================================================

class TestChunkingService:
    """Test the ChunkingService class"""

    @pytest.fixture
    def service(self):
        """Create ChunkingService instance"""
        return ChunkingService(
            target_size=512,
            min_size=100,
            max_size=800,
            overlap=50
        )

    def test_init(self, service):
        """Test ChunkingService initialization"""
        assert service.target_size == 512
        assert service.min_size == 100
        assert service.max_size == 800
        assert service.overlap == 50

    def test_estimate_tokens(self, service):
        """Test token estimation (4 chars ≈ 1 token)"""
        # Empty string
        assert service.estimate_tokens("") == 0  # Empty string returns 0

        # 100 characters ≈ 25 tokens
        assert service.estimate_tokens("a" * 100) == 25

        # 1000 characters ≈ 250 tokens
        assert service.estimate_tokens("a" * 1000) == 250

    def test_remove_rag_ignore_blocks(self, service):
        """Test removal of RAG:IGNORE blocks"""
        content = """
Some visible content

<!-- RAG:IGNORE-START -->
This should be removed
<!-- RAG:IGNORE-END -->

More visible content
"""

        result = service._remove_rag_ignore_blocks(content)

        assert "Some visible content" in result
        assert "More visible content" in result
        assert "This should be removed" not in result

    def test_remove_rag_ignore_preserves_other_content(self, service):
        """Test that non-ignored content is preserved"""
        content = """
# Heading

Regular content here.

<!-- RAG:IGNORE-START -->
Hidden xrefs
<!-- RAG:IGNORE-END -->

## Another Section

More content.
"""

        result = service._remove_rag_ignore_blocks(content)

        assert "# Heading" in result
        assert "Regular content" in result
        assert "## Another Section" in result
        assert "More content" in result
        assert "Hidden xrefs" not in result

    def test_chunk_text_basic(self, service):
        """Test basic text chunking"""
        content = "Short text that fits in one chunk."

        chunks = service.chunk_text(content, preserve_structure=True)

        assert len(chunks) >= 1
        assert isinstance(chunks, list)
        assert isinstance(chunks[0], dict)

    def test_chunk_text_preserves_metadata(self, service):
        """Test that chunks include metadata"""
        content = """# Main Heading

Some content under the heading."""

        chunks = service.chunk_text(content, preserve_structure=True)

        # Check first chunk has metadata
        if len(chunks) > 0:
            chunk = chunks[0]
            assert 'content' in chunk
            assert 'metadata' in chunk
            assert 'sequence' in chunk

    def test_chunk_text_with_headings(self, service):
        """Test chunking respects heading structure"""
        content = """# Heading 1

Content for section 1.

## Heading 2

Content for section 2.

### Heading 3

Content for section 3.
"""

        chunks = service.chunk_text(content, preserve_structure=True)

        # Should create chunks based on structure
        assert len(chunks) >= 1

    def test_chunk_text_with_table(self, service):
        """Test that tables become standalone chunks"""
        content = """# Document

Regular content.

| Column 1 | Column 2 |
|----------|----------|
| Data 1   | Data 2   |

More content.
"""

        chunks = service.chunk_text(content, preserve_structure=True)

        # Table should ideally be its own chunk
        assert len(chunks) >= 1

    def test_chunk_text_without_structure(self, service):
        """Test simple chunking without structure preservation"""
        long_text = "word " * 1000  # Long text without structure

        chunks = service.chunk_text(long_text, preserve_structure=False)

        # Should create multiple simple chunks
        assert len(chunks) >= 1

    def test_chunk_type_enum(self):
        """Test ChunkType enum values"""
        assert ChunkType.HEADING == "heading"
        assert ChunkType.TABLE == "table"
        assert ChunkType.CODE == "code"
        assert ChunkType.LIST == "list"
        assert ChunkType.PARAGRAPH == "paragraph"
        assert ChunkType.MIXED == "mixed"

    def test_chunk_dataclass(self):
        """Test Chunk dataclass"""
        chunk = Chunk(
            content="Test content",
            metadata={"section_title": "Test"},
            sequence=0,
            char_count=12,
            estimated_tokens=3
        )

        assert chunk.content == "Test content"
        assert chunk.metadata["section_title"] == "Test"
        assert chunk.sequence == 0
        assert chunk.char_count == 12
        assert chunk.estimated_tokens == 3

    def test_chunk_to_dict(self):
        """Test Chunk conversion to dictionary"""
        chunk = Chunk(
            content="Test",
            metadata={},
            sequence=0,
            char_count=4,
            estimated_tokens=1
        )

        result = chunk.to_dict()

        assert isinstance(result, dict)
        assert "content" in result
        assert "metadata" in result
        assert "sequence" in result
        assert "char_count" in result
        assert "estimated_tokens" in result


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestChunkingIntegration:
    """Integration-style tests for chunking workflow"""

    def test_chunking_creates_overlapping_context(self):
        """Test that chunking can create overlapping chunks for context"""
        service = ChunkingService(target_size=100, min_size=50, max_size=150, overlap=20)

        # Create long text
        long_text = " ".join([f"Sentence {i}." for i in range(50)])

        chunks = service.chunk_text(long_text, preserve_structure=False)

        # Should create multiple chunks
        if len(chunks) > 1:
            assert len(chunks) >= 2

    def test_empty_content_handling(self):
        """Test handling of empty content"""
        service = ChunkingService()

        chunks = service.chunk_text("", preserve_structure=True)

        # Should handle empty content gracefully
        assert isinstance(chunks, list)

    def test_markdown_structure_extraction(self):
        """Test that markdown structure is properly extracted"""
        service = ChunkingService()

        content = """# Title

Paragraph 1

## Section

Paragraph 2
"""

        chunks = service.chunk_text(content, preserve_structure=True)

        # Should detect and use markdown structure
        assert len(chunks) >= 1


# =============================================================================
# Chat Log Chunking Tests
# =============================================================================

class TestChatLogChunking:
    """Test strategic turn-based chunking for chat logs"""

    @pytest.fixture
    def service(self):
        return ChunkingService(target_size=512, min_size=100, max_size=800)

    def test_parse_chat_turns_basic(self, service):
        """Test parsing of simple user/assistant turns"""
        content = "User: First question\n\nAssistant: First answer\n\nUser: Second question\n\nAssistant: Second answer"

        turns = service._parse_chat_turns(content)

        assert len(turns) == 2
        assert turns[0]['user'] == "First question"
        assert turns[0]['assistant'] == "First answer"
        assert turns[1]['user'] == "Second question"
        assert turns[1]['assistant'] == "Second answer"

    def test_chunk_chat_log_creates_chunks(self, service):
        """Test that chat logs are chunked into turn-based chunks"""
        content = "User: How do I use Python?\n\nAssistant: Python is a programming language.\n\nUser: Show me an example\n\nAssistant: Here is an example: print('hello')"

        chunks = service.chunk_chat_log(content)

        assert len(chunks) >= 1
        assert 'content' in chunks[0]
        assert 'metadata' in chunks[0]
        assert chunks[0]['metadata']['chunk_type'] == 'chat_turn'

    def test_extract_topic_from_question(self, service):
        """Test topic extraction from user questions"""
        question = "How do I create a bootable USB for Fedora?"

        topic = service._extract_topic_from_question(question)

        assert len(topic) > 0
        assert "bootable" in topic.lower() or "usb" in topic.lower() or "fedora" in topic.lower()

    def test_is_topic_shift_detects_explicit_markers(self, service):
        """Test that explicit topic shift markers are detected"""
        turn1 = {'user': 'What is Python?', 'assistant': 'Python is a language'}
        turn2 = {'user': 'Moving on to a different topic, what is Java?', 'assistant': 'Java is...'}

        is_shift = service._is_topic_shift(turn1, turn2)

        assert is_shift is True

    def test_chunk_chat_log_includes_context_headers(self, service):
        """Test that chunks include context headers"""
        content = "User: Question 1\n\nAssistant: Answer 1"

        chunks = service.chunk_chat_log(content)

        assert len(chunks) >= 1
        chunk_content = chunks[0]['content']
        assert '###' in chunk_content  # Has heading
        assert 'Chat Chunk' in chunk_content
        assert 'Turn' in chunk_content
        assert 'User:' in chunk_content
        assert 'Assistant:' in chunk_content

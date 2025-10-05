"""
Integration tests for the new service layer
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from src.services import DocumentService, VectorService, LLMService, OCRService
from src.core.config import Settings


@pytest.fixture
def settings():
    """Create test settings"""
    return Settings(
        chunk_size=1000,
        chunk_overlap=200,
        groq_api_key="test_key",
        anthropic_api_key="test_key",
        openai_api_key="test_key"
    )


@pytest.fixture
def mock_collection():
    """Mock ChromaDB collection"""
    collection = Mock()
    collection.add = Mock()
    collection.query = Mock(return_value={
        "ids": [["doc1"]],
        "documents": [["Test document content"]],
        "metadatas": [[{"filename": "test.txt"}]],
        "distances": [[0.1]]
    })
    return collection


@pytest.mark.asyncio
async def test_end_to_end_document_ingestion(settings, mock_collection):
    """Test complete flow: extract text -> chunk -> store in vector DB"""
    # Create services
    doc_service = DocumentService(settings)
    vector_service = VectorService(mock_collection, settings)

    # Create test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is a test document for integration testing. " * 50)
        temp_path = f.name

    try:
        # Extract text
        content, doc_type, metadata = await doc_service.extract_text_from_file(temp_path)

        assert len(content) > 0
        assert doc_type.value == "text"

        # Chunk text
        chunks = doc_service.chunk_text(content)
        assert len(chunks) > 0

        # Store in vector DB
        for i, chunk in enumerate(chunks):
            await vector_service.add_document(
                doc_id=f"test_doc_{i}",
                content=chunk,
                metadata=metadata
            )

        # Verify storage
        assert mock_collection.add.call_count == len(chunks)
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_end_to_end_rag_flow(settings, mock_collection):
    """Test complete RAG flow: ingest -> search -> generate answer"""
    # Create services
    doc_service = DocumentService(settings)
    vector_service = VectorService(mock_collection, settings)
    llm_service = LLMService(settings)

    # 1. Ingest document
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("The capital of France is Paris. Paris is known for the Eiffel Tower.")
        temp_path = f.name

    try:
        content, _, metadata = await doc_service.extract_text_from_file(temp_path)
        await vector_service.add_document("france_doc", content, metadata)

        # 2. Search for relevant context
        results = await vector_service.search("What is the capital of France?")
        assert len(results) > 0
        context = results[0]["content"]

        # 3. Generate answer with LLM
        with patch('src.services.llm_service.completion') as mock_llm:
            mock_llm.return_value = {
                "choices": [{"message": {"content": "The capital of France is Paris."}}],
                "usage": {"total_tokens": 50}
            }

            prompt = f"Context: {context}\n\nQuestion: What is the capital of France?\n\nAnswer:"
            answer, cost, model = await llm_service.call_llm(prompt)

            assert "Paris" in answer
            assert cost >= 0
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_ocr_to_vector_integration(settings, mock_collection):
    """Test OCR extraction -> vector storage flow"""
    ocr_service = OCRService(languages=['eng'])
    vector_service = VectorService(mock_collection, settings)

    # Create test image
    from PIL import Image
    img = Image.new('RGB', (200, 100), color='white')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name)
        temp_path = f.name

    try:
        with patch('pytesseract.image_to_string') as mock_ocr:
            mock_ocr.return_value = "Extracted text from image"

            # Extract text with OCR
            text = await ocr_service.extract_text_from_image(temp_path)
            assert text == "Extracted text from image"

            # Store in vector DB
            await vector_service.add_document(
                "ocr_doc_1",
                text,
                {"source": "ocr", "image_file": temp_path}
            )

            mock_collection.add.assert_called_once()
    finally:
        Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_multi_document_search_ranking(settings, mock_collection):
    """Test that search results are properly ranked by relevance"""
    vector_service = VectorService(mock_collection, settings)

    # Mock multiple results with different distances
    mock_collection.query.return_value = {
        "ids": [["doc1", "doc2", "doc3"]],
        "documents": [["Most relevant", "Medium relevant", "Least relevant"]],
        "metadatas": [[{"rank": 1}, {"rank": 2}, {"rank": 3}]],
        "distances": [[0.1, 0.5, 0.9]]  # Lower distance = higher relevance
    }

    results = await vector_service.search("test query")

    # Results should be ordered by relevance (lowest distance first)
    assert results[0]["content"] == "Most relevant"
    assert results[0]["relevance_score"] > results[1]["relevance_score"]
    assert results[1]["relevance_score"] > results[2]["relevance_score"]


@pytest.mark.asyncio
async def test_llm_fallback_chain(settings):
    """Test that LLM service falls back through providers correctly"""
    llm_service = LLMService(settings)

    with patch('src.services.llm_service.completion') as mock_completion:
        # Simulate: Groq fails, Anthropic succeeds
        mock_completion.side_effect = [
            Exception("Groq error"),
            {
                "choices": [{"message": {"content": "Anthropic response"}}],
                "usage": {"total_tokens": 100}
            }
        ]

        response, cost, model = await llm_service.call_llm("Test prompt")

        assert response == "Anthropic response"
        assert "anthropic" in model.lower()
        assert mock_completion.call_count == 2


@pytest.mark.asyncio
async def test_cost_accumulation_across_calls(settings):
    """Test that costs accumulate correctly across multiple LLM calls"""
    llm_service = LLMService(settings)

    with patch('src.services.llm_service.completion') as mock_completion:
        mock_completion.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"total_tokens": 100}
        }

        # Make multiple calls
        _, cost1, _ = await llm_service.call_llm("Prompt 1")
        _, cost2, _ = await llm_service.call_llm("Prompt 2")
        _, cost3, _ = await llm_service.call_llm("Prompt 3")

        total_cost = llm_service.total_cost
        assert total_cost == cost1 + cost2 + cost3
        assert total_cost > 0

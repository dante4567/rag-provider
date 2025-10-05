"""
Unit tests for VectorService
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.services.vector_service import VectorService
from src.core.config import Settings


@pytest.fixture
def settings():
    """Create test settings"""
    return Settings(
        chroma_host="localhost",
        chroma_port=8000,
        collection_name="test_collection"
    )


@pytest.fixture
def mock_collection():
    """Create mock ChromaDB collection"""
    collection = Mock()
    collection.name = "test_collection"
    collection.add = Mock()
    collection.query = Mock(return_value={
        "ids": [["doc1", "doc2"]],
        "documents": [["Content 1", "Content 2"]],
        "metadatas": [[{"key": "value1"}, {"key": "value2"}]],
        "distances": [[0.1, 0.2]]
    })
    collection.get = Mock(return_value={
        "ids": ["doc1"],
        "documents": ["Content 1"],
        "metadatas": [{"key": "value1"}]
    })
    collection.delete = Mock()
    return collection


@pytest.fixture
def vector_service(mock_collection, settings):
    """Create VectorService instance with mocked collection"""
    return VectorService(mock_collection, settings)


@pytest.mark.asyncio
async def test_add_document(vector_service, mock_collection):
    """Test adding a document to the vector store"""
    doc_id = "test_doc_123"
    content = "This is test content for the vector store"
    metadata = {"filename": "test.txt", "source": "test"}

    await vector_service.add_document(doc_id, content, metadata)

    mock_collection.add.assert_called_once()
    call_args = mock_collection.add.call_args[1]
    assert doc_id in call_args["ids"]
    assert content in call_args["documents"]
    assert metadata in call_args["metadatas"]


@pytest.mark.asyncio
async def test_search(vector_service, mock_collection):
    """Test searching the vector store"""
    query = "test query"
    top_k = 5

    results = await vector_service.search(query=query, top_k=top_k)

    mock_collection.query.assert_called_once()
    call_args = mock_collection.query.call_args[1]
    assert call_args["query_texts"] == [query]
    assert call_args["n_results"] == top_k

    # Verify result format
    assert len(results) == 2
    assert results[0]["content"] == "Content 1"
    assert results[0]["relevance_score"] == 0.9  # 1 - 0.1 distance
    assert results[0]["metadata"] == {"key": "value1"}


@pytest.mark.asyncio
async def test_search_with_filter(vector_service, mock_collection):
    """Test searching with metadata filter"""
    query = "test query"
    filter_dict = {"filename": "test.txt"}

    results = await vector_service.search(query=query, filter=filter_dict)

    call_args = mock_collection.query.call_args[1]
    assert call_args["where"] == filter_dict


@pytest.mark.asyncio
async def test_get_document(vector_service, mock_collection):
    """Test retrieving a specific document by ID"""
    doc_id = "doc1"

    result = await vector_service.get_document(doc_id)

    mock_collection.get.assert_called_once_with(ids=[doc_id])
    assert result["id"] == doc_id
    assert result["content"] == "Content 1"
    assert result["metadata"] == {"key": "value1"}


@pytest.mark.asyncio
async def test_delete_document(vector_service, mock_collection):
    """Test deleting a document"""
    doc_id = "doc_to_delete"

    await vector_service.delete_document(doc_id)

    mock_collection.delete.assert_called_once_with(ids=[doc_id])


@pytest.mark.asyncio
async def test_search_empty_results(vector_service, mock_collection):
    """Test handling of empty search results"""
    mock_collection.query.return_value = {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]]
    }

    results = await vector_service.search(query="no matches")

    assert results == []


@pytest.mark.asyncio
async def test_relevance_score_calculation(vector_service, mock_collection):
    """Test that relevance scores are calculated correctly from distances"""
    mock_collection.query.return_value = {
        "ids": [["doc1", "doc2", "doc3"]],
        "documents": [["Content 1", "Content 2", "Content 3"]],
        "metadatas": [[{}, {}, {}]],
        "distances": [[0.0, 0.5, 1.0]]  # Perfect match, medium, no match
    }

    results = await vector_service.search(query="test")

    assert results[0]["relevance_score"] == 1.0  # 1 - 0.0
    assert results[1]["relevance_score"] == 0.5  # 1 - 0.5
    assert results[2]["relevance_score"] == 0.0  # 1 - 1.0


@pytest.mark.asyncio
async def test_add_document_with_chunking(vector_service):
    """Test adding document with multiple chunks"""
    doc_id = "chunked_doc"
    chunks = ["Chunk 1 content", "Chunk 2 content", "Chunk 3 content"]
    metadata = {"filename": "large.txt"}

    await vector_service.add_documents_bulk(doc_id, chunks, metadata)

    # Should create chunk IDs like doc_id_0, doc_id_1, etc.
    assert vector_service.collection.add.call_count == 1
    call_args = vector_service.collection.add.call_args[1]
    assert len(call_args["ids"]) == 3
    assert all(doc_id in chunk_id for chunk_id in call_args["ids"])

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
    chunks = ["This is test content for the vector store"]
    metadata = {"filename": "test.txt", "source": "test"}

    await vector_service.add_document(doc_id, chunks, metadata)

    mock_collection.add.assert_called_once()
    call_args = mock_collection.add.call_args[1]
    assert f"{doc_id}_chunk_0" in call_args["ids"]
    assert chunks[0] in call_args["documents"]


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

    # Mock the get method to return document data
    mock_collection.get.return_value = {
        "ids": ["doc1_chunk_0"],
        "documents": ["Content 1"],
        "metadatas": [{"key": "value1", "doc_id": doc_id}]
    }

    result = await vector_service.get_document(doc_id)

    # Verify it called get with the doc_id filter
    call_args = mock_collection.get.call_args[1]
    assert call_args["where"] == {"doc_id": doc_id}
    assert result is not None
    assert doc_id in str(result)


@pytest.mark.asyncio
async def test_delete_document(vector_service, mock_collection):
    """Test deleting a document"""
    doc_id = "doc_to_delete"

    # Mock get to return chunks for this document
    mock_collection.get.return_value = {
        "ids": ["doc_to_delete_chunk_0", "doc_to_delete_chunk_1"],
        "metadatas": [{"doc_id": doc_id}, {"doc_id": doc_id}]
    }

    await vector_service.delete_document(doc_id)

    # Verify it fetched chunks first
    get_call_args = mock_collection.get.call_args[1]
    assert get_call_args["where"] == {"doc_id": doc_id}

    # Verify it deleted the chunks
    delete_call_args = mock_collection.delete.call_args[1]
    assert "doc_to_delete_chunk_0" in delete_call_args["ids"]


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

    result = await vector_service.add_document(doc_id, chunks, metadata)

    # Should return number of chunks added
    assert result == 3

    # Should create chunk IDs like doc_id_chunk_0, doc_id_chunk_1, etc.
    assert vector_service.collection.add.call_count == 1
    call_args = vector_service.collection.add.call_args[1]
    assert len(call_args["ids"]) == 3
    assert all("chunked_doc_chunk_" in chunk_id for chunk_id in call_args["ids"])

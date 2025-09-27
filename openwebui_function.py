"""
OpenWebUI Function for RAG Knowledge Base Integration

Add this function to your OpenWebUI instance to enable knowledge base search.

Installation:
1. Copy this entire function
2. Go to OpenWebUI Admin Panel → Functions
3. Click "Create New Function"
4. Paste the code below
5. Save and enable the function

Usage:
- "Search the knowledge base for machine learning concepts"
- "What does the documentation say about API authentication?"
- "Find information about Docker configuration"
"""

def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """
    Search the RAG knowledge base for relevant information.

    This function connects to your local RAG service to search through
    your ingested documents and return relevant content.

    Args:
        query (str): The search query text
        top_k (int): Number of results to return (default: 5, max: 20)

    Returns:
        str: Formatted search results with content and metadata

    Example:
        search_knowledge_base("machine learning algorithms", 3)
    """
    import requests
    import json
    from typing import Dict, Any

    # Configuration
    RAG_SERVICE_URL = "http://localhost:8001"  # Adjust if needed
    TIMEOUT_SECONDS = 10

    # Validate inputs
    if not query or not query.strip():
        return "❌ Search query cannot be empty."

    if top_k < 1:
        top_k = 1
    elif top_k > 20:
        top_k = 20

    query = query.strip()

    try:
        # Prepare search request
        search_payload = {
            "text": query,
            "top_k": top_k
        }

        # Make request to RAG service
        response = requests.post(
            f"{RAG_SERVICE_URL}/search",
            json=search_payload,
            timeout=TIMEOUT_SECONDS,
            headers={"Content-Type": "application/json"}
        )

        # Handle response
        if response.status_code == 200:
            data = response.json()

            if not data.get('results'):
                return f"🔍 No relevant information found for: '{query}'"

            # Format results for LLM context
            result_count = len(data['results'])
            search_time = data.get('search_time_ms', 0)

            context = f"📚 **Knowledge Base Search Results**\\n"
            context += f"Query: *{query}*\\n"
            context += f"Found: {result_count} result(s) in {search_time:.1f}ms\\n\\n"

            for i, result in enumerate(data['results'], 1):
                relevance = result.get('relevance_score', 0)
                content = result.get('content', '').strip()
                metadata = result.get('metadata', {})

                # Extract useful metadata
                filename = metadata.get('filename', 'Unknown')
                doc_type = metadata.get('document_type', '')
                topics = metadata.get('topics', [])

                # Format individual result
                context += f"**📄 Result {i}** (Relevance: {relevance:.2f})\\n"

                if content:
                    # Truncate very long content
                    if len(content) > 1000:
                        content = content[:1000] + "..."

                    context += f"{content}\\n\\n"

                # Add metadata info
                meta_info = f"*Source: {filename}"
                if doc_type:
                    meta_info += f" | Type: {doc_type}"
                if topics:
                    topic_str = ", ".join(topics[:3])  # Show max 3 topics
                    meta_info += f" | Topics: {topic_str}"
                meta_info += "*\\n"

                context += meta_info
                context += "---\\n\\n"

            # Add usage note
            context += "💡 *This information was retrieved from your knowledge base. "
            context += "You can add more documents by uploading files to the RAG service.*"

            return context

        elif response.status_code == 404:
            return f"❌ RAG service not found at {RAG_SERVICE_URL}. Please check if the service is running."

        elif response.status_code == 503:
            return "⚠️  RAG service is temporarily unavailable. Please try again in a moment."

        else:
            return f"❌ Search failed with status {response.status_code}: {response.text}"

    except requests.exceptions.ConnectionError:
        return f"🔌 Cannot connect to RAG service at {RAG_SERVICE_URL}. Please ensure the service is running."

    except requests.exceptions.Timeout:
        return f"⏱️  Search request timed out after {TIMEOUT_SECONDS} seconds. Please try again."

    except requests.exceptions.RequestException as e:
        return f"❌ Network error during search: {str(e)}"

    except json.JSONDecodeError:
        return "❌ Invalid response from RAG service. Please check service logs."

    except Exception as e:
        return f"❌ Unexpected error during knowledge base search: {str(e)}"


def get_knowledge_base_stats() -> str:
    """
    Get statistics about the knowledge base.

    Returns:
        str: Formatted statistics about documents, chunks, and storage
    """
    import requests

    RAG_SERVICE_URL = "http://localhost:8001"

    try:
        response = requests.get(f"{RAG_SERVICE_URL}/stats", timeout=5)

        if response.status_code == 200:
            data = response.json()

            stats = f"📊 **Knowledge Base Statistics**\\n\\n"
            stats += f"📚 Total Documents: {data.get('total_documents', 0)}\\n"
            stats += f"🧩 Total Chunks: {data.get('total_chunks', 0)}\\n"
            stats += f"💾 Storage Used: {data.get('storage_used_mb', 0):.2f} MB\\n"

            last_ingestion = data.get('last_ingestion')
            if last_ingestion:
                stats += f"⏰ Last Update: {last_ingestion}\\n"

            return stats

        else:
            return f"❌ Could not retrieve stats: HTTP {response.status_code}"

    except Exception as e:
        return f"❌ Error getting knowledge base stats: {str(e)}"


def list_knowledge_base_documents() -> str:
    """
    List all documents in the knowledge base.

    Returns:
        str: Formatted list of documents with metadata
    """
    import requests

    RAG_SERVICE_URL = "http://localhost:8001"

    try:
        response = requests.get(f"{RAG_SERVICE_URL}/documents", timeout=10)

        if response.status_code == 200:
            documents = response.json()

            if not documents:
                return "📭 Knowledge base is empty. Upload some documents to get started!"

            doc_list = f"📋 **Knowledge Base Documents** ({len(documents)} total)\\n\\n"

            for i, doc in enumerate(documents[:10], 1):  # Show max 10 documents
                filename = doc.get('filename', 'Unknown')
                chunks = doc.get('chunks', 0)
                created = doc.get('created_at', '')
                doc_id = doc.get('id', '')[:8]  # Show short ID

                doc_list += f"**{i}. {filename}**\\n"
                doc_list += f"   • ID: {doc_id}...\\n"
                doc_list += f"   • Chunks: {chunks}\\n"
                doc_list += f"   • Created: {created[:10] if created else 'Unknown'}\\n\\n"

            if len(documents) > 10:
                doc_list += f"... and {len(documents) - 10} more documents\\n"

            return doc_list

        else:
            return f"❌ Could not retrieve documents: HTTP {response.status_code}"

    except Exception as e:
        return f"❌ Error listing documents: {str(e)}"


# Export functions for OpenWebUI
__all__ = ['search_knowledge_base', 'get_knowledge_base_stats', 'list_knowledge_base_documents']
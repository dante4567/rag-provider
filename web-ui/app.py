import gradio as gr
import requests
import json
import os
from datetime import datetime

RAG_URL = "http://localhost:8001"

def check_health():
    """Check if RAG service is healthy"""
    try:
        response = requests.get(f"{RAG_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return f"✅ Service Healthy\n\n{json.dumps(data, indent=2)}"
        return f"❌ Service returned {response.status_code}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def upload_document(files):
    """Upload document(s) to RAG service"""
    try:
        if files is None:
            return "❌ No file selected"

        # Handle both single file and multiple files
        if not isinstance(files, list):
            files = [files]

        results = []
        total_success = 0
        total_failed = 0

        for file in files:
            try:
                # Gradio provides the full path in file.name, extract just the filename
                filename = os.path.basename(file.name)

                # Read file content into memory to avoid file handle issues
                with open(file.name, 'rb') as f:
                    file_content = f.read()

                file_data = {"file": (filename, file_content, 'application/octet-stream')}
                response = requests.post(f"{RAG_URL}/ingest/file", files=file_data, timeout=120)

                if response.status_code == 200:
                    data = response.json()
                    metadata = data.get('metadata', {})

                    result = f"✅ **{filename}**\n"
                    result += f"  • Chunks: {data.get('chunks', 0)}\n"
                    result += f"  • Domain: {metadata.get('domain', 'N/A')}\n"
                    result += f"  • Significance: {metadata.get('significance_score', 0):.3f}\n"
                    result += f"  • Quality: {metadata.get('quality_tier', 'N/A')}\n"

                    # Show duplicate warning
                    if metadata.get('is_duplicate'):
                        result += f"  • ⚠️ DUPLICATE DETECTED\n"

                    # Show top 3 tags (handle both string and list formats)
                    tags_raw = metadata.get('tags', '')
                    if isinstance(tags_raw, str):
                        # Tags stored as comma-separated string
                        tags = [t.strip() for t in tags_raw.split(',') if t.strip()][:3]
                    else:
                        # Already a list
                        tags = tags_raw[:3]

                    if tags:
                        result += f"  • Tags: {', '.join(tags)}\n"

                    results.append(result)
                    total_success += 1
                else:
                    results.append(f"❌ **{filename}**: Failed ({response.status_code})")
                    total_failed += 1
            except Exception as e:
                results.append(f"❌ **{filename}**: {str(e)[:100]}")
                total_failed += 1

        # Summary
        summary = f"## Upload Summary\n"
        summary += f"✅ Success: {total_success} | ❌ Failed: {total_failed}\n\n"
        summary += "---\n\n"
        summary += "\n\n".join(results)

        return summary
    except Exception as e:
        return f"❌ Error: {str(e)}"

def search_documents(query, max_results=5):
    """Search documents"""
    try:
        if not query.strip():
            return "❌ Please enter a search query"

        payload = {"text": query, "top_k": int(max_results)}
        response = requests.post(f"{RAG_URL}/search", json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()

            # Format results nicely
            results = data.get('results', [])
            if not results:
                return "No results found."

            results_text = f"Found {len(results)} results:\n\n"
            for i, result in enumerate(results, 1):
                metadata = result.get('metadata', {})
                results_text += f"**{i}. {metadata.get('title', 'Untitled')}**\n"
                results_text += f"  Score: {result.get('score', 0):.4f}\n"
                results_text += f"  Domain: {metadata.get('domain', 'N/A')}\n"
                results_text += f"  Significance: {metadata.get('significance_score', 0):.3f}\n"

                # Content preview
                content = result.get('content', '')
                preview = content[:200] + "..." if len(content) > 200 else content
                results_text += f"  Content: {preview}\n"

                # Tags (handle both string and list formats)
                tags_raw = metadata.get('tags', '')
                if isinstance(tags_raw, str):
                    # Tags stored as comma-separated string in ChromaDB
                    tags = [t.strip() for t in tags_raw.split(',') if t.strip()][:5]
                else:
                    # Already a list
                    tags = tags_raw[:5]

                if tags:
                    results_text += f"  Tags: {', '.join(tags)}\n"

                results_text += "\n"

            return results_text
        return f"❌ Search failed: {response.status_code}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def chat_with_docs(question, model="groq/llama-3.1-8b-instant"):
    """Chat with RAG"""
    try:
        if not question.strip():
            return "❌ Please enter a question"

        payload = {"question": question, "llm_model": model}
        response = requests.post(f"{RAG_URL}/chat", json=payload, timeout=60)

        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', 'No answer generated')
            sources = data.get('sources', [])
            cost = data.get('cost', 0)

            result = f"**Answer:**\n{answer}\n\n"
            result += f"💰 **Cost:** ${cost:.6f}\n"
            result += f"🤖 **Model:** {model}\n\n"

            if sources:
                result += f"**Sources ({len(sources)}):**\n"
                for i, source in enumerate(sources[:5], 1):
                    result += f"{i}. {source.get('title', 'Untitled')}\n"
                if len(sources) > 5:
                    result += f"... and {len(sources) - 5} more sources\n"

            return result
        return f"❌ Chat failed: {response.status_code}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def get_stats():
    """Get service statistics"""
    try:
        response = requests.get(f"{RAG_URL}/stats", timeout=10)
        if response.status_code == 200:
            data = response.json()

            stats_text = "📊 **Service Statistics**\n\n"

            # Documents
            if 'total_documents' in data:
                stats_text += f"**Documents:** {data['total_documents']}\n"

            # Chunks
            if 'total_chunks' in data:
                stats_text += f"**Total Chunks:** {data['total_chunks']}\n"
                if data['total_documents'] > 0:
                    avg_chunks = data['total_chunks'] / data['total_documents']
                    stats_text += f"**Average Chunks/Doc:** {avg_chunks:.1f}\n"

            # Storage
            if 'storage_used_mb' in data:
                stats_text += f"**Storage Used:** {data['storage_used_mb']:.2f} MB\n"

            # Last ingestion
            if 'last_ingestion' in data:
                stats_text += f"\n**Last Ingestion:** {data['last_ingestion']}\n"

            # LLM providers
            if 'llm_provider_status' in data:
                stats_text += f"\n**LLM Providers:**\n"
                for provider, status in data['llm_provider_status'].items():
                    icon = "✅" if status else "❌"
                    stats_text += f"  {icon} {provider}\n"

            # OCR
            if 'ocr_available' in data:
                icon = "✅" if data['ocr_available'] else "❌"
                stats_text += f"\n**OCR Available:** {icon}\n"

            return stats_text
        return f"❌ Failed to get stats: {response.status_code}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Build Gradio interface
with gr.Blocks(title="RAG Service Interface", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🤖 RAG Service - Document Processing & Search")
    gr.Markdown("*Multi-stage enrichment with tag learning and duplicate detection*")

    # Health check at top
    with gr.Row():
        health_btn = gr.Button("🏥 Check Service Health", variant="secondary")
    with gr.Row():
        health_output = gr.Textbox(label="Service Status", lines=10)
    health_btn.click(check_health, outputs=health_output)

    gr.Markdown("---")

    # Main tabs
    with gr.Tabs():
        # Upload tab
        with gr.Tab("📤 Upload"):
            gr.Markdown("### Upload documents for processing with multi-stage enrichment")
            gr.Markdown("Supported: PDF, TXT, MD, DOCX, DOC, EML, RTF, HTML, XML")

            with gr.Row():
                with gr.Column(scale=1):
                    file_input = gr.File(
                        label="Select Document(s)",
                        file_types=[".pdf", ".txt", ".md", ".docx", ".doc", ".eml", ".rtf", ".html", ".xml"],
                        file_count="multiple"
                    )
                    upload_btn = gr.Button("📤 Upload & Process", variant="primary", size="lg")
                with gr.Column(scale=2):
                    upload_output = gr.Textbox(label="Upload Results", lines=20)

            upload_btn.click(upload_document, inputs=file_input, outputs=upload_output)

            gr.Markdown("**💡 Tip:** Select multiple files to batch upload! Upload similar documents to test tag learning!")

        # Search tab
        with gr.Tab("🔍 Search"):
            gr.Markdown("### Vector search across all documents")

            with gr.Row():
                with gr.Column(scale=1):
                    search_input = gr.Textbox(
                        label="Search Query",
                        placeholder="Enter your search query...",
                        lines=2
                    )
                    max_results = gr.Slider(
                        minimum=1,
                        maximum=20,
                        value=5,
                        step=1,
                        label="Max Results"
                    )
                    search_btn = gr.Button("🔍 Search", variant="primary", size="lg")
                with gr.Column(scale=2):
                    search_output = gr.Textbox(label="Search Results", lines=20)

            search_btn.click(
                search_documents,
                inputs=[search_input, max_results],
                outputs=search_output
            )

        # Chat tab
        with gr.Tab("💬 Chat"):
            gr.Markdown("### Ask questions about your documents")

            with gr.Row():
                with gr.Column(scale=1):
                    chat_input = gr.Textbox(
                        label="Question",
                        placeholder="What are the main topics in my documents?",
                        lines=3
                    )
                    model_select = gr.Dropdown(
                        choices=[
                            "groq/llama-3.1-8b-instant",
                            "anthropic/claude-3-5-sonnet-latest",
                            "openai/gpt-4o-mini",
                            "google/gemini-2.0-flash"
                        ],
                        value="groq/llama-3.1-8b-instant",
                        label="LLM Model"
                    )
                    chat_btn = gr.Button("💬 Ask", variant="primary", size="lg")
                with gr.Column(scale=2):
                    chat_output = gr.Textbox(label="Answer", lines=20)

            chat_btn.click(
                chat_with_docs,
                inputs=[chat_input, model_select],
                outputs=chat_output
            )

            gr.Markdown("**💰 Cost Estimates:**")
            gr.Markdown("- Groq (Llama 3.1): ~$0.0001/query")
            gr.Markdown("- Claude Sonnet: ~$0.01-0.03/query")
            gr.Markdown("- GPT-4o-mini: ~$0.001/query")

        # Stats tab
        with gr.Tab("📊 Statistics"):
            gr.Markdown("### Service statistics and monitoring")

            with gr.Row():
                stats_btn = gr.Button("🔄 Refresh Stats", variant="secondary", size="lg")
            with gr.Row():
                stats_output = gr.Textbox(label="Statistics", lines=20)

            stats_btn.click(get_stats, outputs=stats_output)

    # Footer
    gr.Markdown("---")
    gr.Markdown("### 📈 Current State: B+ (83/100)")
    gr.Markdown("**✅ Proven:** Tag learning (38.3% diverse, 62.3% similar) | Duplicate detection (100%) | API enrichment working")
    gr.Markdown("**⚠️ Unknown:** Scale (100+ docs) | Performance (large PDFs) | Tag learning across domains")
    gr.Markdown("**🎯 Goal:** Upload 50+ documents and discover what breaks!")

# Launch
if __name__ == "__main__":
    print("=" * 80)
    print("🚀 RAG Service Web UI")
    print("=" * 80)
    print(f"Starting Gradio interface at http://127.0.0.1:7860")
    print(f"Connecting to RAG service at {RAG_URL}")
    print("=" * 80)

    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False
    )

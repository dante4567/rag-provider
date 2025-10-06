# Adding Frontends to RAG Provider

**Date**: October 5, 2025
**Current State**: B+ (85/100) - Ready for heavy testing
**Goal**: Add frontends to facilitate testing with 50-100 real documents

---

## Why Add Frontends Now?

You've proven the core works (tag learning 62.3%, duplicate detection 100%, Obsidian export functional) but only with ~15 documents.

**Frontends aren't features - they're testing tools.**

Adding Telegram bot + Web UI makes it **easy to upload your next 50-100 documents** and discover what breaks at scale.

---

## Architecture Decision

**These frontends are STANDALONE** - they connect directly to RAG service at `http://localhost:8001`

There are also **unified frontends** in the ai-ecosystem-integrated repo that connect to a gateway (localhost:8003) which orchestrates multiple services. Those are separate.

```
rag-provider/          # This repo - standalone frontends
├── telegram-bot/     # Direct connection to localhost:8001
└── web-ui/          # Direct connection to localhost:8001

ai-ecosystem-integrated/   # Other repo - unified frontends
└── ai-telegram-bots/
    └── unified_bot.py    # Connects to gateway at localhost:8003
```

---

## Implementation Order

### 1. Telegram Bot (2 hours) - DO THIS FIRST

**Why first?** Easiest way to start uploading real documents from phone/desktop.

**Steps**:

```bash
cd /path/to/rag-provider
mkdir telegram-bot
cd telegram-bot
```

**Create `telegram-bot/rag_bot.py`**:

Copy this complete file from ai-ecosystem-integrated/ai-telegram-bots/rag_bot.py but change line 25:

```python
# Change from:
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://localhost:8001")  # Already correct!

# Make sure it says localhost:8001 (direct to RAG service, not gateway)
```

Actually, the existing rag_bot.py from ecosystem already defaults to localhost:8001, so just copy it:

```bash
cp ../../ai-ecosystem-integrated/ai-telegram-bots/rag_bot.py .
```

**Create `telegram-bot/requirements.txt`**:
```
python-telegram-bot==20.6
aiohttp>=3.8.0
```

**Setup and run**:
```bash
pip install -r requirements.txt

# Get bot token from @BotFather on Telegram
export TELEGRAM_BOT_TOKEN="your_token_here"

# Make sure RAG service is running
cd .. && docker-compose up -d

# Run bot
cd telegram-bot
python rag_bot.py
```

**Test**:
- Send `/start` to your bot
- Upload a PDF
- Search with `/search AI`
- Chat naturally: "What is this document about?"

### 2. Web UI with Gradio (4-6 hours) - DO THIS NEXT

**Why Gradio?** Better for document upload/search than Streamlit. Simple to implement.

**Steps**:

```bash
cd /path/to/rag-provider
mkdir web-ui
cd web-ui
```

**Create `web-ui/requirements.txt`**:
```
gradio>=4.0.0
requests>=2.31.0
python-dateutil>=2.8.2
```

**Create `web-ui/app.py`**:

```python
import gradio as gr
import requests
import json
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

def upload_document(file):
    """Upload document to RAG service"""
    try:
        if file is None:
            return "❌ No file selected"

        with open(file.name, 'rb') as f:
            files = {"file": (file.name, f)}
            response = requests.post(f"{RAG_URL}/ingest/file", files=files, timeout=120)

        if response.status_code == 200:
            data = response.json()
            return f"✅ Upload successful!\n\n{json.dumps(data, indent=2)}"
        return f"❌ Upload failed: {response.status_code}\n{response.text}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def search_documents(query, max_results=5):
    """Search documents"""
    try:
        payload = {"text": query, "top_k": int(max_results)}
        response = requests.post(f"{RAG_URL}/search", json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()

            # Format results nicely
            results_text = f"Found {len(data.get('results', []))} results:\n\n"
            for i, result in enumerate(data.get('results', []), 1):
                results_text += f"**{i}. {result.get('metadata', {}).get('title', 'Untitled')}**\n"
                results_text += f"Score: {result.get('score', 0):.4f}\n"
                results_text += f"Content: {result.get('content', '')[:200]}...\n"
                results_text += f"Tags: {', '.join(result.get('metadata', {}).get('tags', []))}\n\n"

            return results_text
        return f"❌ Search failed: {response.status_code}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def chat_with_docs(question, model="groq/llama-3.1-8b-instant"):
    """Chat with RAG"""
    try:
        payload = {"question": question, "llm_model": model}
        response = requests.post(f"{RAG_URL}/chat", json=payload, timeout=60)

        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', 'No answer generated')
            sources = data.get('sources', [])
            cost = data.get('cost', 0)

            result = f"**Answer:**\n{answer}\n\n"
            result += f"**Cost:** ${cost:.6f}\n\n"
            if sources:
                result += "**Sources:**\n"
                for source in sources[:3]:
                    result += f"- {source.get('title', 'Untitled')}\n"
            return result
        return f"❌ Chat failed: {response.status_code}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def get_stats():
    """Get service statistics"""
    try:
        response = requests.get(f"{RAG_URL}/stats", timeout=10)
        if response.status_code == 200:
            return json.dumps(response.json(), indent=2)
        return f"❌ Failed to get stats: {response.status_code}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Build Gradio interface
with gr.Blocks(title="RAG Service Interface") as demo:
    gr.Markdown("# RAG Service - Document Processing & Search")
    gr.Markdown("*Multi-stage enrichment with tag learning and duplicate detection*")

    # Health check at top
    with gr.Row():
        health_btn = gr.Button("🏥 Check Service Health", variant="secondary")
        health_output = gr.Textbox(label="Service Status", lines=10)
        health_btn.click(check_health, outputs=health_output)

    # Main tabs
    with gr.Tabs():
        # Upload tab
        with gr.Tab("📤 Upload"):
            gr.Markdown("Upload documents for processing with multi-stage enrichment")
            with gr.Row():
                with gr.Column():
                    file_input = gr.File(
                        label="Select Document",
                        file_types=[".pdf", ".txt", ".md", ".docx", ".doc", ".eml"]
                    )
                    upload_btn = gr.Button("Upload & Process", variant="primary")
                with gr.Column():
                    upload_output = gr.Textbox(label="Upload Result", lines=15)

            upload_btn.click(upload_document, inputs=file_input, outputs=upload_output)

        # Search tab
        with gr.Tab("🔍 Search"):
            gr.Markdown("Vector search across all documents")
            with gr.Row():
                with gr.Column():
                    search_input = gr.Textbox(
                        label="Search Query",
                        placeholder="Enter your search query..."
                    )
                    max_results = gr.Slider(
                        minimum=1,
                        maximum=20,
                        value=5,
                        step=1,
                        label="Max Results"
                    )
                    search_btn = gr.Button("Search", variant="primary")
                with gr.Column():
                    search_output = gr.Textbox(label="Search Results", lines=20)

            search_btn.click(
                search_documents,
                inputs=[search_input, max_results],
                outputs=search_output
            )

        # Chat tab
        with gr.Tab("💬 Chat"):
            gr.Markdown("Ask questions about your documents")
            with gr.Row():
                with gr.Column():
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
                    chat_btn = gr.Button("Ask", variant="primary")
                with gr.Column():
                    chat_output = gr.Textbox(label="Answer", lines=20)

            chat_btn.click(
                chat_with_docs,
                inputs=[chat_input, model_select],
                outputs=chat_output
            )

        # Stats tab
        with gr.Tab("📊 Statistics"):
            gr.Markdown("Service statistics and monitoring")
            stats_btn = gr.Button("Refresh Stats", variant="secondary")
            stats_output = gr.Textbox(label="Statistics", lines=20)
            stats_btn.click(get_stats, outputs=stats_output)

    # Footer
    gr.Markdown("---")
    gr.Markdown("**Current State:** B+ (85/100) - Proven with 15 docs, ready for scale testing")
    gr.Markdown("**Known Limits:** Untested at 100+ docs | Personal KB is toy example | Scale performance unknown")

# Launch
if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False
    )
```

**Run**:
```bash
pip install -r requirements.txt

# Make sure RAG service is running
cd .. && docker-compose up -d

# Run web UI
cd web-ui
python app.py
```

Access at: http://localhost:7860

### 3. OpenWebUI Function (2-3 hours) - OPTIONAL

**When to do this**: After you've tested heavily with Telegram + Web UI

**Steps**:

```bash
cd /path/to/rag-provider
mkdir openwebui
cd openwebui
```

**Create `openwebui/rag_function.py`**:

Copy from ai-ecosystem-integrated/openwebui-configs/rag-only-config.py

The existing file should already work - it connects to localhost:8001 by default.

**Usage**:
1. Copy `rag_function.py` to your OpenWebUI functions directory
2. Restart OpenWebUI
3. Use in chat:
   - `search_documents("AI architecture")`
   - `chat_with_documents("What is microservices?")`

---

## Testing Strategy

### Week 1: Heavy Upload Testing

**Goal**: Upload 50-100 real documents, discover what breaks

**Using Telegram**:
- Upload from phone while commuting
- Mix document types: PDFs, transcripts, notes
- Test with large files (50+ pages)

**Using Web UI**:
- Bulk uploads
- Monitor tag learning dashboard
- Check cost tracking
- Review Obsidian exports

**What to monitor**:
1. **Tag learning**: Are tags being reused within domains?
2. **Performance**: Do large PDFs timeout?
3. **Memory**: Does the service leak memory?
4. **Costs**: Is $0.010577/doc accurate for YOUR documents?
5. **Quality**: Are Obsidian exports matching your needs?

### Week 2: Fix What Breaks

Based on Week 1 findings:
- Optimize slow operations
- Fix crashes/errors
- Enhance Obsidian export
- Adjust tag taxonomy thresholds

**Target**: Get from B+ (85/100) to A- (88/100)

---

## Known Issues to Watch For

From the B+ (85/100) assessment, these are UNKNOWN and may surface during testing:

1. **Tag Learning at Scale**
   - ✅ Works for 5 similar documents (62.3% reuse)
   - ❓ Will it work across 20 different domains?
   - ❓ Will tags bleed between unrelated topics?

2. **Performance**
   - ❓ 50-page PDFs - timeout?
   - ❓ Concurrent uploads - crash?
   - ❓ Memory leaks?

3. **Triage Service**
   - ✅ Duplicate detection works (exact matches)
   - ❓ Near-duplicates (95% similar)?
   - ❓ Personal KB (currently hardcoded)?

4. **Obsidian Export**
   - ✅ Generates valid markdown
   - ❓ Matches SmartNotes methodology?
   - ❓ Cross-references useful?

---

## Success Criteria

**After 2 weeks of heavy usage**:

- ✅ Uploaded 100+ documents without major crashes
- ✅ Tag reuse measured across multiple domains
- ✅ Cost tracking validated with diverse document types
- ✅ Performance bottlenecks identified and fixed
- ✅ Obsidian export enhanced based on real needs

**Grade target**: A- (88/100) → "Works well, known limits documented"

---

## What NOT to Do

**Don't add features yet:**
- ❌ Don't build knowledge graph (Phase 2)
- ❌ Don't enhance entity relationships (Phase 2)
- ❌ Don't build Personal KB UI (needs real data first)

**Do test heavily:**
- ✅ Upload real documents
- ✅ Use both frontends daily
- ✅ Document issues
- ✅ Fix what breaks

---

## Questions & Issues

If you encounter problems:

1. **Service won't start**: Check docker-compose logs
2. **Telegram bot crashes**: Check API token, service URL
3. **Upload fails**: Check file size limits, disk space
4. **Search returns nothing**: Check ChromaDB is running
5. **Tags not learning**: Upload more similar docs, check cache refresh

---

**Next Steps**: Start with Telegram bot (2 hours), get it working, upload 10 documents today.

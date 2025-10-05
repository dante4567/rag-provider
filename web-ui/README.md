# Web UI for RAG Service

Gradio-based web interface for testing the RAG provider.

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Make sure RAG service is running:**
```bash
cd .. && docker-compose up -d
```

3. **Run the web UI:**
```bash
python app.py
```

4. **Open in browser:**
```
http://localhost:7860
```

## Features

### 📤 Upload Tab
- Upload documents (PDF, TXT, MD, DOCX, etc.)
- View enrichment results
- See tags, domain classification, quality scores
- Detect duplicates

### 🔍 Search Tab
- Vector search across all documents
- Adjust number of results (1-20)
- See scores, metadata, tags
- Preview content

### 💬 Chat Tab
- Ask questions about your documents
- Choose LLM model:
  - Groq/Llama 3.1 (fast, cheap)
  - Claude Sonnet (quality, expensive)
  - GPT-4o-mini (balanced)
  - Gemini 2.0 Flash (Google)
- See cost per query
- View sources used

### 📊 Statistics Tab
- Document counts by collection
- Total cost tracking
- Service health

## Testing Strategy

### Week 1: Heavy Upload Testing

**Goal:** Upload 50-100 documents, discover what breaks

1. **Upload diverse documents:**
   - PDFs (small, medium, large)
   - Text files
   - Markdown notes
   - Word documents

2. **Monitor tag learning:**
   - Upload 5 similar documents
   - Check if tags are being reused
   - Aim for 60%+ tag reuse on similar docs

3. **Test duplicate detection:**
   - Upload same file twice
   - Should see "DUPLICATE DETECTED"

4. **Check cost tracking:**
   - Upload 10 documents
   - Verify cost is ~$0.01 per document

5. **Review Obsidian exports:**
   - Check `obsidian/` directory
   - Verify markdown is valid
   - Check if tags match SmartNotes methodology

### What to Monitor

1. **Performance:**
   - Do large PDFs timeout?
   - Does upload speed slow down after 50 docs?
   - Any memory leaks?

2. **Quality:**
   - Are tags useful?
   - Is domain classification accurate?
   - Are significance scores reasonable?

3. **Errors:**
   - Do certain file types fail?
   - Any crashes or exceptions?
   - ChromaDB issues?

## Troubleshooting

**Web UI won't start:**
```bash
# Check if port 7860 is in use
lsof -i :7860

# Try different port
# Edit app.py line 310: server_port=7861
```

**Service health check fails:**
```bash
# Check RAG service
curl http://localhost:8001/health

# Check Docker
docker-compose ps
docker-compose logs rag-service
```

**Upload fails:**
- Check file size (< 50MB recommended)
- Check file type is supported
- Check disk space
- Check Docker logs

**Search returns nothing:**
- Upload documents first
- Check ChromaDB: `docker-compose logs chromadb`
- Try simpler search terms

## Configuration

Default RAG service URL: `http://localhost:8001`

To change, edit `app.py` line 6:
```python
RAG_URL = "http://your-server:8001"
```

## Tips

- **Batch uploads:** Upload multiple documents back-to-back to test concurrency
- **Tag learning:** Upload 5 similar documents (e.g., 5 research papers) and check tag reuse
- **Cost tracking:** Monitor total costs in Statistics tab
- **Obsidian export:** Check generated files in `obsidian/` directory

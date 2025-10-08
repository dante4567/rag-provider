# Frontend Integration Guide - RAG Provider

## Overview

The RAG Provider exposes a REST API that can be integrated with any frontend. This guide covers:
1. Terminal/CLI usage
2. OpenWebUI integration
3. Web UI (Gradio)
4. Custom frontends
5. API reference

---

## 1. Terminal / CLI Usage

### Basic Commands

```bash
# Health check
curl http://localhost:8001/health | jq

# Upload document
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@document.pdf" \
  -F "generate_obsidian=true" | jq

# Search
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"text":"legal custody decision","top_k":5}' | jq

# Chat (RAG-powered Q&A)
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"What are the custody arrangements?","top_k":3}' | jq '.answer'

# Get stats
curl http://localhost:8001/stats | jq
```

### Pretty Output with jq

```bash
# Format search results
curl -s -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"text":"school enrollment","top_k":3}' \
  | jq '.results[] | {
      title: .metadata.title,
      score: (.relevance_score * 100 | floor),
      topics: .metadata.topics
    }'

# Show document list
curl -s http://localhost:8001/documents \
  | jq '.[] | {filename, chunks, created_at}'
```

### Shell Functions (Add to ~/.bashrc or ~/.zshrc)

```bash
# RAG search
rag-search() {
  curl -s -X POST http://localhost:8001/search \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"$1\",\"top_k\":${2:-5}}" \
    | jq '.results[] | {title: .metadata.title, score: .relevance_score}'
}

# RAG chat
rag-ask() {
  curl -s -X POST http://localhost:8001/chat \
    -H "Content-Type: application/json" \
    -d "{\"query\":\"$1\",\"top_k\":3}" \
    | jq -r '.answer'
}

# RAG ingest
rag-ingest() {
  for file in "$@"; do
    echo "Ingesting: $(basename $file)"
    curl -s -X POST http://localhost:8001/ingest/file \
      -F "file=@$file" \
      -F "generate_obsidian=true" \
      | jq '{success, doc_id, chunks}'
  done
}

# Usage:
# rag-search "court decision" 3
# rag-ask "What are the school enrollment deadlines?"
# rag-ingest ~/Documents/legal/*.pdf
```

---

## 2. OpenWebUI Integration

### Setup

```bash
# 1. Run OpenWebUI
docker run -d \
  --name open-webui \
  -p 3000:8080 \
  -e OPENAI_API_BASE_URL=http://host.docker.internal:8001 \
  -e OPENAI_API_KEY=dummy \
  ghcr.io/open-webui/open-webui:main

# 2. Configure RAG Provider as external knowledge base
```

### OpenWebUI Function (RAG Integration)

Create this as an OpenWebUI function:

```python
"""
title: RAG Provider Search
description: Search your personal RAG knowledge base
author: Your Name
version: 1.0
"""

import requests
from pydantic import BaseModel, Field
from typing import Optional

class Tools:
    class Valves(BaseModel):
        RAG_API_URL: str = Field(
            default="http://host.docker.internal:8001",
            description="RAG Provider API URL"
        )

    def __init__(self):
        self.valves = self.Valves()

    def search_rag(
        self,
        query: str,
        top_k: int = 5,
        __user__: dict = {}
    ) -> str:
        """
        Search your personal RAG knowledge base

        :param query: Search query
        :param top_k: Number of results
        :return: Search results
        """
        try:
            response = requests.post(
                f"{self.valves.RAG_API_URL}/search",
                json={"text": query, "top_k": top_k},
                timeout=30
            )
            response.raise_for_status()
            results = response.json()

            output = f"Found {results['total_results']} results:\n\n"
            for i, result in enumerate(results['results'], 1):
                title = result['metadata'].get('title', 'Untitled')
                score = result['relevance_score'] * 100
                content_preview = result['content'][:200]

                output += f"{i}. **{title}** ({score:.0f}% relevant)\n"
                output += f"   {content_preview}...\n\n"

            return output

        except Exception as e:
            return f"Error searching RAG: {str(e)}"
```

### OpenWebUI Workflow

1. **Upload documents** via RAG Provider API
2. **Ask questions** in OpenWebUI chat
3. **Auto-search RAG** using the function above
4. **Get answers** with source citations

Example chat:
```
User: What are the school enrollment deadlines?
Assistant: [Searches RAG] Based on your documents, the deadline for school enrollment in NRW is November 15, 2025.
```

---

## 3. Web UI (Gradio)

### Quick Start

```bash
cd web-ui
pip install -r requirements.txt
python app.py
# Open http://localhost:7860
```

### Features
- **Drag & drop** document upload
- **Search interface** with filters
- **Chat interface** for Q&A
- **Document browser** with metadata

### Customization

```python
# web-ui/app.py
import gradio as gr
import requests

def upload_document(file):
    files = {'file': open(file.name, 'rb')}
    data = {'generate_obsidian': 'true'}
    response = requests.post('http://localhost:8001/ingest/file', files=files, data=data)
    return response.json()

def search_documents(query, top_k):
    response = requests.post(
        'http://localhost:8001/search',
        json={'text': query, 'top_k': top_k}
    )
    results = response.json()['results']
    return "\n\n".join([
        f"**{r['metadata']['title']}**\n{r['content'][:200]}..."
        for r in results
    ])

with gr.Blocks() as demo:
    gr.Markdown("# RAG Provider")

    with gr.Tab("Upload"):
        file_input = gr.File(label="Upload Document")
        upload_btn = gr.Button("Upload")
        upload_output = gr.JSON(label="Result")
        upload_btn.click(upload_document, inputs=file_input, outputs=upload_output)

    with gr.Tab("Search"):
        query_input = gr.Textbox(label="Search Query")
        topk_input = gr.Slider(1, 10, value=5, step=1, label="Number of Results")
        search_btn = gr.Button("Search")
        search_output = gr.Markdown(label="Results")
        search_btn.click(search_documents, inputs=[query_input, topk_input], outputs=search_output)

demo.launch(server_name="0.0.0.0", server_port=7860)
```

---

## 4. Custom Frontend Integration

### React Example

```javascript
// src/api/rag.js
const RAG_API_URL = 'http://localhost:8001';

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('generate_obsidian', 'true');

  const response = await fetch(`${RAG_API_URL}/ingest/file`, {
    method: 'POST',
    body: formData
  });

  return response.json();
}

export async function searchDocuments(query, topK = 5) {
  const response = await fetch(`${RAG_API_URL}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: query, top_k: topK })
  });

  return response.json();
}

export async function chatRAG(query) {
  const response = await fetch(`${RAG_API_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, top_k: 3 })
  });

  return response.json();
}

// Usage in component
import { uploadDocument, searchDocuments, chatRAG } from './api/rag';

function App() {
  const [results, setResults] = useState([]);

  const handleSearch = async (query) => {
    const data = await searchDocuments(query, 5);
    setResults(data.results);
  };

  return (
    <div>
      <input type="text" onChange={(e) => handleSearch(e.target.value)} />
      {results.map(r => (
        <div key={r.chunk_id}>
          <h3>{r.metadata.title}</h3>
          <p>{r.content}</p>
          <span>Relevance: {(r.relevance_score * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  );
}
```

### Vue.js Example

```vue
<template>
  <div>
    <input v-model="query" @input="search" placeholder="Search..." />
    <div v-for="result in results" :key="result.chunk_id" class="result">
      <h3>{{ result.metadata.title }}</h3>
      <p>{{ result.content.substring(0, 200) }}...</p>
      <span>{{ (result.relevance_score * 100).toFixed(0) }}% relevant</span>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      query: '',
      results: []
    };
  },
  methods: {
    async search() {
      if (!this.query) return;

      const response = await fetch('http://localhost:8001/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: this.query, top_k: 5 })
      });

      const data = await response.json();
      this.results = data.results;
    }
  }
};
</script>
```

---

## 5. API Reference

### Endpoints

#### Health Check
```http
GET /health
```

Response:
```json
{
  "status": "healthy",
  "chromadb": "connected",
  "total_models_available": 11
}
```

#### Upload Document
```http
POST /ingest/file
Content-Type: multipart/form-data

file: [binary]
generate_obsidian: true
process_ocr: false
```

Response:
```json
{
  "success": true,
  "doc_id": "abc123",
  "chunks": 15,
  "metadata": {
    "title": "Document Title",
    "keywords": {
      "primary": ["legal/court/decision"]
    }
  },
  "obsidian_path": "/data/obsidian/2025-10-08__pdf__document__abc1.md"
}
```

#### Search
```http
POST /search
Content-Type: application/json

{
  "text": "query text",
  "top_k": 5,
  "filter": {}
}
```

Response:
```json
{
  "query": "query text",
  "results": [
    {
      "content": "Chunk content...",
      "metadata": {
        "title": "Document Title",
        "topics": ["legal/court/decision"],
        "dates": ["2025-10-08"]
      },
      "relevance_score": 0.95,
      "chunk_id": "abc123_chunk_1"
    }
  ],
  "total_results": 5,
  "search_time_ms": 123.45
}
```

#### Chat (RAG-powered Q&A)
```http
POST /chat
Content-Type: application/json

{
  "query": "What are the custody arrangements?",
  "top_k": 3
}
```

Response:
```json
{
  "answer": "Based on the court decision...",
  "sources": [
    {
      "title": "Court Decision",
      "chunk_id": "abc123_chunk_1",
      "relevance_score": 0.95
    }
  ],
  "confidence": 0.92
}
```

#### Get Stats
```http
GET /stats
```

Response:
```json
{
  "total_documents": 150,
  "total_chunks": 1234,
  "storage_used_mb": 12.5,
  "last_ingestion": "2025-10-08T14:25:16",
  "llm_provider_status": {
    "groq": true,
    "anthropic": true,
    "openai": true
  }
}
```

---

## 6. Authentication (Future)

### API Key Setup (Not Yet Implemented)

```bash
# In .env
API_KEY_ENABLED=true
API_KEYS=key1,key2,key3
```

### Usage with API Key

```bash
curl -H "X-API-Key: your-key-here" \
  http://localhost:8001/search \
  -d '{"text":"query"}'
```

### Python with API Key

```python
import requests

headers = {'X-API-Key': 'your-key-here'}
response = requests.post(
    'http://localhost:8001/search',
    json={'text': 'query', 'top_k': 5},
    headers=headers
)
```

---

## 7. Deployment Options

### Local (Development)
```bash
docker-compose up
# Access at http://localhost:8001
```

### Expose to Network (Home Server)
```yaml
# docker-compose.yml
services:
  rag-service:
    ports:
      - "0.0.0.0:8001:8000"  # Accessible from network
```

### Reverse Proxy (Nginx)
```nginx
server {
    listen 80;
    server_name rag.local;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Tailscale (Remote Access)
```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Connect
tailscale up

# Access from anywhere on your Tailnet
# http://your-machine-name:8001
```

---

## Next Steps

1. **Try terminal commands** - Test with `rag-search` and `rag-ask` functions
2. **Set up OpenWebUI** - Install and configure RAG integration
3. **Build custom UI** - Use React/Vue examples
4. **Mobile access** - Use Tailscale for remote API access

See `EDGE_CASE_IMPROVEMENT_GUIDE.md` for how to improve the system with your own feedback and edge cases.
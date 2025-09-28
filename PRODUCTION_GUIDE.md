# Production RAG Service - Complete Guide

## 🚀 **Quick Start**

```bash
# 1. Clone and setup
git clone <repo>
cd rag-provider
cp .env.example .env

# 2. Add your API keys to .env
GROQ_API_KEY=your_groq_key
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key

# 3. Deploy
chmod +x create_volumes.sh && ./create_volumes.sh
docker-compose up -d

# 4. Upload documents
curl -X POST -F "file=@document.pdf" http://localhost:8000/upload

# 5. Search and chat
curl "http://localhost:8000/search?query=your+question"
```

## 📊 **Production Costs (Real Usage)**

| Usage Level | Monthly Cost | Best For |
|-------------|--------------|----------|
| **Small Team** (100 docs/month) | $5-15 | Startups, small businesses |
| **Medium Business** (500 docs/month) | $30-50 | Growing companies |
| **Enterprise** (1000+ docs/month) | $100-500 | Large organizations |

*Compared to alternatives: 70-95% cost savings*

## ⚙️ **Key Features**

- **Multi-Provider LLM**: Groq (ultra-cheap) → Anthropic → OpenAI fallbacks
- **Document Processing**: PDFs, Office docs, emails, images (13+ formats)
- **Advanced Search**: Vector + reranking for better accuracy
- **Cost Optimization**: Smart provider selection saves 70-95% on LLM costs
- **Obsidian Export**: Rich metadata markdown for knowledge management

## 🔧 **Production Configuration**

### **Environment Variables**
```bash
# Required
GROQ_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Optional
GOOGLE_API_KEY=your_key_here
DAILY_LLM_BUDGET=10.0
ENABLE_OBSIDIAN_EXPORT=true
```

### **Docker Deployment**
```yaml
# Recommended production setup
services:
  rag_service:
    build: .
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./data:/data
    restart: unless-stopped
```

## 🎯 **Production Readiness**

### **✅ Production Ready**
- Basic RAG pipeline (upload → search → chat)
- Multi-format document processing
- Cost-effective LLM usage with fallbacks
- Docker deployment with persistence

### **⚠️ Needs Work (1-2 weeks)**
- OCR for scanned documents (currently broken)
- Monitoring and alerting
- Load testing for concurrent users

### **❌ Not Ready (3-6 months)**
- Enterprise authentication/authorization
- Multi-tenancy support
- SOC2 compliance features

## 💡 **Cost Optimization Tips**

1. **Use Groq for bulk processing** - 80% cheaper than premium options
2. **Reserve premium models** for critical analysis only
3. **Set daily budgets** to prevent cost overruns
4. **Monitor usage** via provider dashboards (LiteLLM tracking inconsistent)

## 🚨 **Known Issues**

- **Image OCR**: Broken, needs tesseract debugging
- **Cost tracking**: Returns $0.00 for some providers (use dashboards)
- **Performance**: sentence-transformers models slow to load initially

## 📈 **Scaling Guidelines**

- **Up to 1K docs**: Single Docker instance sufficient
- **1K-10K docs**: Add monitoring, consider load balancing
- **10K+ docs**: Redesign for horizontal scaling

---
*Last updated: 2025-09-28*
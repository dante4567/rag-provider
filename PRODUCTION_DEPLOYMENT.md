# Production RAG Service Deployment Guide

## 🎯 FastAPI & NixOS Context

### Why FastAPI isn't available on the host system:
- **NixOS Environment**: The host system uses NixOS with limited package availability
- **Permission Restrictions**: System-level package installation requires elevated permissions
- **Design Philosophy**: Production services should run in isolated containers, not on the host

### ✅ This is the CORRECT production setup:

```
┌─────────────────┐    ┌─────────────────────────────────────┐
│   Host System   │    │          Docker Containers          │
│   (NixOS)       │    │                                     │
│                 │    │  ┌─────────────┐  ┌─────────────┐   │
│ • Basic Python  │────┤  │ RAG Service │  │  ChromaDB   │   │
│ • Docker        │    │  │             │  │             │   │
│ • Enhanced      │    │  │ • FastAPI   │  │ • Vector DB │   │
│   modules       │    │  │ • uvicorn   │  │ • Persistent│   │
│                 │    │  │ • All deps  │  │   storage   │   │
│                 │    │  └─────────────┘  └─────────────┘   │
│                 │    │           │                         │
│                 │    │  ┌─────────────┐                    │
│                 │    │  │    Nginx    │                    │
│                 │    │  │ Reverse     │                    │
│                 │    │  │ Proxy       │                    │
│                 │    │  └─────────────┘                    │
└─────────────────┘    └─────────────────────────────────────┘
```

## 🚀 Production Deployment

### Quick Start:
```bash
# 1. Configure API keys
cp .env.example .env
# Edit .env with your API keys

# 2. Deploy with one command
./deploy.sh
```

### Manual Deployment:
```bash
# 1. Create directories
mkdir -p data/{input,output,processed,obsidian} volumes/chroma_data

# 2. Build and start services
docker-compose build --no-cache
docker-compose up -d

# 3. Verify services
curl http://localhost:8001/health
curl http://localhost:8001/search/config
```

## 🔧 Enhanced API Endpoints

### Production-Ready Features:
- **`POST /search/enhanced`** - Hybrid retrieval with reranking
- **`POST /chat/enhanced`** - Enhanced RAG chat
- **`POST /triage/document`** - Document quality assessment
- **`GET /search/config`** - Configuration and status
- **`POST /admin/initialize-enhanced`** - Initialize enhanced features

### Example Usage:
```bash
# Enhanced search
curl -X POST http://localhost:8001/search/enhanced \
  -H "Content-Type: application/json" \
  -d '{
    "text": "machine learning algorithms",
    "top_k": 5,
    "use_hybrid": true,
    "use_reranker": true
  }'

# Enhanced chat
curl -X POST http://localhost:8001/chat/enhanced \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is deep learning?",
    "max_context_chunks": 5,
    "use_hybrid": true,
    "use_reranker": true
  }'

# Document triage
curl -X POST http://localhost:8001/triage/document \
  -F "file=@document.txt"
```

## 🔒 Production Security

### Nginx Reverse Proxy Features:
- **Rate Limiting**: API calls throttled per IP
- **Security Headers**: XSS protection, content type validation
- **SSL/TLS Support**: HTTPS with certificate mounting
- **Access Logging**: Request monitoring and analytics

### Environment Variables:
```bash
# Core LLM APIs (at least one required)
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here

# Cloud OCR APIs (optional)
GOOGLE_VISION_API_KEY=your_key_here
AZURE_CV_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_CV_API_KEY=your_key_here
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_key_here
```

## 📊 Monitoring & Health Checks

### Service Health:
```bash
# Check all services
docker-compose ps

# View logs
docker-compose logs -f rag-service
docker-compose logs -f chromadb
docker-compose logs -f nginx

# Health endpoints
curl http://localhost:8001/health      # RAG service
curl http://localhost:8000/api/v1/heartbeat  # ChromaDB
curl http://localhost/api/health       # Via Nginx
```

### Performance Monitoring:
```bash
# Resource usage
docker stats

# Service-specific metrics
curl http://localhost:8001/search/config
```

## 🔄 Scaling & Production Tips

### For High-Traffic Deployments:
1. **Increase worker count** in docker-compose.yml:
   ```yaml
   command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4"]
   ```

2. **Add Redis caching** for search results
3. **Use external ChromaDB cluster** for scalability
4. **Configure SSL certificates** in nginx/ssl/ directory
5. **Set up monitoring** with Prometheus + Grafana

### Resource Requirements:
- **Minimum**: 2GB RAM, 2 CPU cores, 10GB storage
- **Recommended**: 4GB RAM, 4 CPU cores, 50GB storage
- **High-traffic**: 8GB+ RAM, 8+ CPU cores, 100GB+ storage

## ✅ Verification Checklist

- [ ] All Docker containers running
- [ ] ChromaDB accessible on port 8000
- [ ] RAG service healthy on port 8001
- [ ] Enhanced endpoints responding
- [ ] API keys configured in .env
- [ ] Nginx proxy (optional) on port 80
- [ ] Document processing working
- [ ] Obsidian vault generation enabled
- [ ] Cloud OCR providers configured (optional)

## 🎉 Success Indicators

When properly deployed, you should see:
```
✅ ChromaDB is healthy
✅ RAG Service is healthy
✅ Enhanced search available
✅ Quality triage working
✅ Cloud OCR configured
🎉 Production RAG Service with Enhanced Features is now running!
```

## 🆘 Troubleshooting

### Common Issues:
1. **FastAPI import error on host**: Normal - runs in Docker
2. **Permission denied**: Use `sudo` for Docker commands if needed
3. **Port conflicts**: Stop other services using ports 8000, 8001, 80
4. **API key errors**: Check .env file configuration
5. **ChromaDB connection**: Ensure containers are on same network

### Debug Commands:
```bash
# Check container logs
docker-compose logs rag-service

# Access container shell
docker-compose exec rag-service bash

# Test API directly
docker-compose exec rag-service python -c "import fastapi; print('FastAPI available')"
```

## 📞 Support

For issues or questions:
1. Check container logs: `docker-compose logs -f`
2. Verify service health: `curl http://localhost:8001/health`
3. Test enhanced features: `python3 docker_integration_test.py`
4. Review configuration: `curl http://localhost:8001/search/config`
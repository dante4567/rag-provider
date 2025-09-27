#!/bin/bash

# Production RAG Service Deployment Script
# ========================================
#
# Deploys the production-ready RAG service with enhanced features
# Designed for NixOS with Docker routing considerations

set -e

echo "🚀 Production RAG Service Deployment"
echo "===================================="

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating data directories..."
mkdir -p data/input data/output data/processed data/obsidian volumes/chroma_data ssl

# Create example .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating example .env file..."
    cat > .env << 'EOF'
# LLM API Keys (at least one required)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
GROQ_API_KEY=your_groq_api_key_here
GOOGLE_API_KEY=your_google_api_key_here

# Cloud OCR API Keys (optional - for enhanced OCR)
GOOGLE_VISION_API_KEY=your_google_vision_api_key_here
AZURE_CV_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_CV_API_KEY=your_azure_cv_api_key_here
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
AWS_REGION=us-east-1

# Security (optional)
SECRET_KEY=your_secret_key_here
EOF
    echo "⚠️  Please edit .env file with your API keys before running!"
fi

# Set permissions
echo "🔧 Setting permissions..."
chmod +x deploy.sh
chmod 755 data data/input data/output data/processed data/obsidian
chmod 755 volumes volumes/chroma_data

# Build and start services
echo "🔨 Building Docker images..."
docker-compose build --no-cache

echo "🚀 Starting production services..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🏥 Checking service health..."

# Check ChromaDB
if curl -s http://localhost:8000/api/v1/heartbeat > /dev/null; then
    echo "✅ ChromaDB is healthy"
else
    echo "❌ ChromaDB is not responding"
fi

# Check RAG Service
if curl -s http://localhost:8001/health > /dev/null; then
    echo "✅ RAG Service is healthy"
else
    echo "❌ RAG Service is not responding"
fi

# Check Nginx (if running)
if curl -s http://localhost/api/health > /dev/null; then
    echo "✅ Nginx proxy is healthy"
else
    echo "⚠️  Nginx proxy not configured (direct access only)"
fi

echo ""
echo "🎉 Deployment Complete!"
echo ""
echo "📋 Service Endpoints:"
echo "   • Main UI:        http://localhost:8001/"
echo "   • Health Check:   http://localhost:8001/health"
echo "   • API Docs:       http://localhost:8001/docs"
echo "   • ChromaDB:       http://localhost:8000/"
echo ""
echo "🔥 Enhanced Features Available:"
echo "   • Enhanced Search:     POST /search/enhanced"
echo "   • Enhanced Chat:       POST /chat/enhanced"
echo "   • Document Triage:     POST /triage/document"
echo "   • Search Config:       GET /search/config"
echo "   • Admin Initialize:    POST /admin/initialize-enhanced"
echo ""
echo "📖 Quick Test Commands:"
echo "   curl http://localhost:8001/health"
echo "   curl http://localhost:8001/search/config"
echo ""
echo "🔄 To restart services:"
echo "   docker-compose restart"
echo ""
echo "🛑 To stop services:"
echo "   docker-compose down"
echo ""
echo "📊 To view logs:"
echo "   docker-compose logs -f rag-service"
echo ""

# Show running containers
echo "📦 Running Containers:"
docker-compose ps

echo ""
echo "✨ Production RAG Service with Enhanced Features is now running!"
echo "🔒 Remember to configure your API keys in .env for full functionality"
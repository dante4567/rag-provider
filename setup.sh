#!/bin/bash

# RAG Service Setup Script
# This script helps you set up the RAG service quickly

set -e

echo "🚀 RAG Service Setup Script"
echo "=========================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📄 Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created. Please edit it with your API keys:"
    echo "   nano .env"
    echo ""
    echo "Required: Add either ANTHROPIC_API_KEY or OPENAI_API_KEY"
    echo ""
    read -p "Press Enter after you've configured your API keys..."
fi

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/input data/markdown data/processed

# Check if .env has API keys
if ! grep -q "^ANTHROPIC_API_KEY=sk-" .env && ! grep -q "^OPENAI_API_KEY=sk-" .env; then
    echo "⚠️  Warning: No API keys found in .env file"
    echo "   Please add either ANTHROPIC_API_KEY or OPENAI_API_KEY"
    echo ""
fi

# Build and start services
echo "🐳 Building and starting services..."
docker-compose up -d --build

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check ChromaDB health
echo "🔍 Checking ChromaDB..."
if curl -s http://localhost:8000/api/v1/heartbeat > /dev/null; then
    echo "✅ ChromaDB is running"
else
    echo "❌ ChromaDB is not responding"
fi

# Check RAG service health
echo "🔍 Checking RAG service..."
if curl -s http://localhost:8001/health > /dev/null; then
    echo "✅ RAG service is running"
else
    echo "❌ RAG service is not responding"
    echo "Check logs with: docker-compose logs rag-service"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Test the service: python test_rag.py"
echo "2. Add documents to: ./data/input/"
echo "3. Access API docs: http://localhost:8001/docs"
echo "4. Check service logs: docker-compose logs -f"
echo ""
echo "Useful commands:"
echo "- Stop services: docker-compose down"
echo "- View logs: docker-compose logs -f rag-service"
echo "- Reset data: docker-compose down -v"
echo ""
# RAG Provider - Development Makefile
# Common commands for development and deployment

.PHONY: help setup up down restart logs logs-follow test test-unit test-integration clean build health status shell

# Default target
help:
	@echo "RAG Provider - Available Commands"
	@echo ""
	@echo "🚀 Deployment:"
	@echo "  make setup          - Initial setup (copy .env.example, create volumes)"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make build          - Rebuild Docker images"
	@echo "  make rebuild        - Clean rebuild (no cache)"
	@echo ""
	@echo "📊 Monitoring:"
	@echo "  make logs           - View logs (last 100 lines)"
	@echo "  make logs-follow    - Follow logs in real-time"
	@echo "  make health         - Check service health"
	@echo "  make status         - Show container status"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  make test           - Run all tests"
	@echo "  make test-unit      - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-service   - Test specific service (e.g., make test-service SERVICE=llm)"
	@echo ""
	@echo "🛠️  Development:"
	@echo "  make shell          - Open shell in RAG service container"
	@echo "  make clean          - Clean up volumes and temp files"
	@echo "  make reset          - Full reset (clean + rebuild + up)"
	@echo ""
	@echo "📝 Documentation:"
	@echo "  make docs           - View project documentation"
	@echo "  make assessment     - View honest assessment"

# Setup and deployment
setup:
	@echo "🔧 Setting up RAG Provider..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✅ Created .env file - EDIT THIS with your API keys!"; \
	else \
		echo "✅ .env file already exists"; \
	fi
	@mkdir -p data/input data/output data/processed data/obsidian data/calendar data/contacts
	@echo "✅ Created data directories"
	@echo ""
	@echo "⚠️  NEXT STEP: Edit .env and add your API keys, then run 'make up'"

up:
	@echo "🚀 Starting RAG Provider services..."
	docker-compose up -d
	@echo "✅ Services started"
	@echo ""
	@echo "🔍 Check health: make health"
	@echo "📊 View logs: make logs-follow"

down:
	@echo "🛑 Stopping RAG Provider services..."
	docker-compose down
	@echo "✅ Services stopped"

restart:
	@echo "🔄 Restarting services..."
	docker-compose restart
	@echo "✅ Services restarted"

build:
	@echo "🏗️  Building Docker images..."
	docker-compose build
	@echo "✅ Build complete"

rebuild:
	@echo "🏗️  Clean rebuild (no cache)..."
	docker-compose build --no-cache
	@echo "✅ Rebuild complete"

# Monitoring
logs:
	@echo "📋 Viewing logs (last 100 lines)..."
	docker-compose logs --tail=100

logs-follow:
	@echo "📋 Following logs (Ctrl+C to stop)..."
	docker-compose logs -f

health:
	@echo "🏥 Checking service health..."
	@curl -s http://localhost:8001/health | jq '.' || echo "❌ Service not responding"

status:
	@echo "📊 Container status:"
	@docker-compose ps

# Testing
test:
	@echo "🧪 Running all tests..."
	docker exec rag_service pytest tests/ -v

test-unit:
	@echo "🧪 Running unit tests..."
	docker exec rag_service pytest tests/unit/ -v

test-integration:
	@echo "🧪 Running integration tests..."
	docker exec rag_service pytest tests/integration/ -v

test-service:
	@if [ -z "$(SERVICE)" ]; then \
		echo "❌ Usage: make test-service SERVICE=llm_service"; \
	else \
		echo "🧪 Testing $(SERVICE)..."; \
		docker exec rag_service pytest tests/unit/test_$(SERVICE).py -v; \
	fi

# Development
shell:
	@echo "🐚 Opening shell in RAG service container..."
	docker exec -it rag_service /bin/bash

clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v
	rm -rf data/output/* data/processed/* data/obsidian/*.md data/calendar/*.ics data/contacts/*.vcf
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

reset:
	@echo "🔄 Full reset (clean + rebuild + up)..."
	@make clean
	@make rebuild
	@make up
	@echo "✅ Reset complete"

# Documentation
docs:
	@echo "📚 Project Documentation:"
	@echo ""
	@echo "Core Docs:"
	@echo "  README.md                          - Project overview"
	@echo "  CLAUDE.md                          - Development guide"
	@echo "  HONEST_ASSESSMENT_2025-10-08.md    - Detailed assessment"
	@echo ""
	@echo "View with: less README.md"

assessment:
	@less HONEST_ASSESSMENT_2025-10-08.md

# Quick commands (shortcuts)
.PHONY: start stop ps
start: up
stop: down
ps: status

#!/bin/bash
# Wipe contaminated data and re-ingest everything

set -e

echo "🗑️  WIPING CONTAMINATED DATA..."
echo ""

# 1. Stop services
echo "1️⃣ Stopping services..."
docker-compose stop rag-service

# 2. Wipe ChromaDB (nuclear option - clean slate)
echo "2️⃣ Wiping ChromaDB..."
docker-compose stop chromadb
docker volume rm rag-provider_chroma_data 2>/dev/null || true
docker-compose up -d chromadb
sleep 5

# 3. Backup obsidian vault (just in case)
echo "3️⃣ Backing up obsidian vault..."
timestamp=$(date +%Y%m%d_%H%M%S)
if [ -d "data/obsidian" ]; then
    tar -czf "data/obsidian_backup_${timestamp}.tar.gz" data/obsidian/
    echo "   ✅ Backup saved: data/obsidian_backup_${timestamp}.tar.gz"
fi

# 4. Wipe obsidian vault
echo "4️⃣ Wiping obsidian vault..."
rm -rf data/obsidian/*
mkdir -p data/obsidian

# 5. Restart RAG service
echo "5️⃣ Restarting RAG service..."
docker-compose up -d rag-service
sleep 10

echo ""
echo "✅ CLEANUP COMPLETE!"
echo ""
echo "📦 Now re-ingest your documents:"
echo "   - LLM chats: python ingest_villa_luna.py (for emails)"
echo "   - Or use: python ingest_all.py"
echo ""

#!/bin/bash
set -e

# RAG System Restore Script
# Restores from a backup created by backup.sh

# Check for backup date argument
if [ -z "$1" ]; then
  echo "Usage: $0 <backup-date>"
  echo ""
  echo "Available backups:"
  ls -1 backups/ | grep "^20" | tail -10
  exit 1
fi

BACKUP_DATE="$1"
BACKUP_PATH="./backups/${BACKUP_DATE}"

# Verify backup exists
if [ ! -d "${BACKUP_PATH}" ]; then
  echo "❌ Backup not found: ${BACKUP_PATH}"
  echo ""
  echo "Available backups:"
  ls -1 backups/ | grep "^20" | tail -10
  exit 1
fi

# Display backup manifest
if [ -f "${BACKUP_PATH}/manifest.txt" ]; then
  echo "📋 Backup Manifest:"
  cat "${BACKUP_PATH}/manifest.txt"
  echo ""
fi

# Confirm restore
read -p "⚠️  This will REPLACE all current data. Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
  echo "❌ Restore cancelled"
  exit 0
fi

echo ""
echo "🔄 Starting restore from ${BACKUP_DATE}..."

# Stop services
echo "🛑 Stopping services..."
docker-compose down

# Restore ChromaDB
if [ -f "${BACKUP_PATH}/chromadb-backup.tar.gz" ]; then
  echo "📦 Restoring ChromaDB..."

  # Remove old volume
  docker volume rm rag_chroma_data 2>/dev/null || true
  docker volume create rag_chroma_data

  # Restore data
  docker run --rm \
    -v rag_chroma_data:/data \
    -v "${PWD}/${BACKUP_PATH}":/backup \
    alpine \
    tar xzf /backup/chromadb-backup.tar.gz -C /data

  echo "✅ ChromaDB restored"
else
  echo "⚠️  No ChromaDB backup found, skipping"
fi

# Restore Obsidian vault
if [ -f "${BACKUP_PATH}/obsidian-vault.tar.gz" ]; then
  echo "📝 Restoring Obsidian vault..."
  rm -rf obsidian_vault
  tar xzf "${BACKUP_PATH}/obsidian-vault.tar.gz"
  echo "✅ Obsidian vault restored"
else
  echo "⚠️  No Obsidian backup found, skipping"
fi

# Restore configuration
if [ -f "${BACKUP_PATH}/.env" ]; then
  echo "⚙️  Restoring configuration..."
  cp "${BACKUP_PATH}/.env" .env
  echo "✅ Configuration restored"
else
  echo "⚠️  No .env backup found, skipping"
fi

# Restore vocabulary
if [ -f "${BACKUP_PATH}/vocabulary.tar.gz" ]; then
  echo "📚 Restoring vocabulary..."
  rm -rf vocabulary
  tar xzf "${BACKUP_PATH}/vocabulary.tar.gz"
  echo "✅ Vocabulary restored"
else
  echo "⚠️  No vocabulary backup found, skipping"
fi

# Restart services
echo ""
echo "🚀 Restarting services..."
docker-compose up -d

# Wait for services
echo "⏳ Waiting for services to start..."
sleep 10

# Verify
echo ""
echo "🔍 Verifying restore..."

# Check health
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
  echo "✅ API is responding"
else
  echo "⚠️  API not responding (may need more time)"
fi

# Check document count
DOC_COUNT=$(curl -s http://localhost:8001/documents 2>/dev/null | jq -r '.total' 2>/dev/null || echo "unknown")
echo "📊 Document count: ${DOC_COUNT}"

echo ""
echo "✅ Restore complete!"
echo ""
echo "Next steps:"
echo "1. Test a search query:"
echo "   curl -X POST http://localhost:8001/search -H 'Content-Type: application/json' -d '{\"text\": \"test\", \"top_k\": 5}'"
echo ""
echo "2. Check logs for errors:"
echo "   docker-compose logs -f rag-service"

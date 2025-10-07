#!/bin/bash
set -e

# RAG System Backup Script
# Creates a complete backup of ChromaDB, Obsidian vault, and configuration

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Create dated backup directory
DATE=$(date +%Y-%m-%d-%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/${DATE}"
mkdir -p "${BACKUP_PATH}"

echo "🔄 Starting RAG system backup..."
echo "Backup location: ${BACKUP_PATH}"

# Backup ChromaDB volume
echo "📦 Backing up ChromaDB vector database..."
docker run --rm \
  -v rag_chroma_data:/data \
  -v "${PWD}/${BACKUP_PATH}":/backup \
  alpine \
  tar czf /backup/chromadb-backup.tar.gz -C /data . 2>/dev/null || {
    echo "⚠️  ChromaDB backup failed (volume may not exist yet)"
    touch "${BACKUP_PATH}/chromadb-backup-empty.txt"
  }

# Backup Obsidian vault
if [ -d "obsidian_vault" ]; then
  echo "📝 Backing up Obsidian vault..."
  tar czf "${BACKUP_PATH}/obsidian-vault.tar.gz" obsidian_vault/ 2>/dev/null || {
    echo "⚠️  Obsidian vault backup failed"
  }
else
  echo "ℹ️  No Obsidian vault to backup"
  touch "${BACKUP_PATH}/obsidian-vault-empty.txt"
fi

# Backup configuration
if [ -f ".env" ]; then
  echo "⚙️  Backing up configuration..."
  cp .env "${BACKUP_PATH}/" 2>/dev/null || {
    echo "⚠️  Configuration backup failed"
  }
else
  echo "ℹ️  No .env file to backup"
fi

# Backup vocabulary
if [ -d "vocabulary" ]; then
  echo "📚 Backing up controlled vocabulary..."
  tar czf "${BACKUP_PATH}/vocabulary.tar.gz" vocabulary/ 2>/dev/null || {
    echo "⚠️  Vocabulary backup failed"
  }
else
  echo "ℹ️  No vocabulary directory to backup"
  touch "${BACKUP_PATH}/vocabulary-empty.txt"
fi

# Create backup manifest
cat > "${BACKUP_PATH}/manifest.txt" <<EOF
RAG System Backup
=================
Date: $(date)
Host: $(hostname)
User: $(whoami)

Contents:
- ChromaDB: $([ -f "${BACKUP_PATH}/chromadb-backup.tar.gz" ] && du -sh "${BACKUP_PATH}/chromadb-backup.tar.gz" | cut -f1 || echo "empty")
- Obsidian: $([ -f "${BACKUP_PATH}/obsidian-vault.tar.gz" ] && du -sh "${BACKUP_PATH}/obsidian-vault.tar.gz" | cut -f1 || echo "empty")
- Config: $([ -f "${BACKUP_PATH}/.env" ] && echo "present" || echo "missing")
- Vocabulary: $([ -f "${BACKUP_PATH}/vocabulary.tar.gz" ] && du -sh "${BACKUP_PATH}/vocabulary.tar.gz" | cut -f1 || echo "empty")

Total backup size: $(du -sh "${BACKUP_PATH}" | cut -f1)
EOF

# Display manifest
cat "${BACKUP_PATH}/manifest.txt"

# Remove old backups
if [ "${RETENTION_DAYS}" -gt 0 ]; then
  echo ""
  echo "🧹 Cleaning up backups older than ${RETENTION_DAYS} days..."
  find "${BACKUP_DIR}" -type d -name "20*" -mtime +${RETENTION_DAYS} -exec rm -rf {} + 2>/dev/null || true
  echo "Current backups:"
  ls -lh "${BACKUP_DIR}" | grep "^d" | tail -5
fi

echo ""
echo "✅ Backup complete: ${BACKUP_PATH}"
echo "Total size: $(du -sh "${BACKUP_PATH}" | cut -f1)"

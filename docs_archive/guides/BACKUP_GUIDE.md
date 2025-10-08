# ChromaDB Backup & Restore Guide

## Overview

This guide covers backing up and restoring your RAG system data, including:
- ChromaDB vector database
- Obsidian vault (generated markdown files)
- Configuration and environment

## What Needs Backup

### 1. ChromaDB Data (Critical)
**Location:** Docker volume `rag_chroma_data`
**Contains:** All document vectors, embeddings, and metadata
**Size:** Grows with document count (~100MB per 1000 documents)

### 2. Obsidian Vault (Important)
**Location:** `./obsidian_vault/` (host directory)
**Contains:** Generated markdown files with entity links
**Size:** Small (~1KB per document)

### 3. Configuration (Important)
**Location:** `.env` file
**Contains:** API keys, settings, customizations
**Size:** < 1KB

### 4. Controlled Vocabulary (Optional)
**Location:** `./vocabulary/` directory
**Contains:** Custom topics, people, places, projects
**Size:** < 100KB

---

## Backup Methods

### Method 1: Docker Volume Backup (Recommended)

**Pros:** Complete, atomic, works with running services
**Cons:** Requires Docker commands

```bash
# Stop services (optional but safer)
docker-compose down

# Create backup directory
mkdir -p backups/$(date +%Y-%m-%d)

# Backup ChromaDB volume
docker run --rm \
  -v rag_chroma_data:/data \
  -v $(pwd)/backups/$(date +%Y-%m-%d):/backup \
  alpine \
  tar czf /backup/chromadb-backup.tar.gz -C /data .

# Backup Obsidian vault (simple copy)
cp -r obsidian_vault backups/$(date +%Y-%m-%d)/

# Backup configuration
cp .env backups/$(date +%Y-%m-%d)/
cp -r vocabulary backups/$(date +%Y-%m-%d)/ 2>/dev/null || true

# Restart services
docker-compose up -d

echo "Backup complete: backups/$(date +%Y-%m-%d)/"
```

### Method 2: Automated Daily Backup (Production)

Create `scripts/backup.sh`:

```bash
#!/bin/bash
set -e

# Configuration
BACKUP_DIR="/path/to/backups"
RETENTION_DAYS=30

# Create dated backup directory
DATE=$(date +%Y-%m-%d)
BACKUP_PATH="${BACKUP_DIR}/${DATE}"
mkdir -p "${BACKUP_PATH}"

# Backup ChromaDB
echo "Backing up ChromaDB..."
docker run --rm \
  -v rag_chroma_data:/data \
  -v "${BACKUP_PATH}":/backup \
  alpine \
  tar czf /backup/chromadb-backup.tar.gz -C /data .

# Backup Obsidian vault
echo "Backing up Obsidian vault..."
tar czf "${BACKUP_PATH}/obsidian-vault.tar.gz" obsidian_vault/

# Backup configuration
echo "Backing up configuration..."
cp .env "${BACKUP_PATH}/" 2>/dev/null || echo "No .env file"
tar czf "${BACKUP_PATH}/vocabulary.tar.gz" vocabulary/ 2>/dev/null || echo "No vocabulary dir"

# Remove old backups
echo "Cleaning up old backups..."
find "${BACKUP_DIR}" -type d -mtime +${RETENTION_DAYS} -exec rm -rf {} + 2>/dev/null || true

echo "✅ Backup complete: ${BACKUP_PATH}"
```

### Method 3: Continuous Sync (Cloud Storage)

For cloud backup (AWS S3, Google Cloud, etc.):

```bash
# Install AWS CLI
# pip install awscli

# Create sync script
#!/bin/bash
# scripts/sync-to-cloud.sh

# Backup locally first
./scripts/backup.sh

# Sync to S3
aws s3 sync /path/to/backups s3://your-bucket/rag-backups/ \
  --exclude "*" \
  --include "*/chromadb-backup.tar.gz" \
  --include "*/obsidian-vault.tar.gz" \
  --include "*/.env"

echo "✅ Cloud sync complete"
```

---

## Restore Process

### Full Restore from Backup

```bash
# Stop services
docker-compose down

# Remove old data (CAREFUL!)
docker volume rm rag_chroma_data
docker volume create rag_chroma_data

# Restore ChromaDB from backup
BACKUP_DATE="2025-10-07"  # Change to your backup date
docker run --rm \
  -v rag_chroma_data:/data \
  -v $(pwd)/backups/${BACKUP_DATE}:/backup \
  alpine \
  tar xzf /backup/chromadb-backup.tar.gz -C /data

# Restore Obsidian vault
rm -rf obsidian_vault
cp -r backups/${BACKUP_DATE}/obsidian_vault .

# Restore configuration
cp backups/${BACKUP_DATE}/.env .
cp -r backups/${BACKUP_DATE}/vocabulary . 2>/dev/null || true

# Restart services
docker-compose up -d

# Wait for services to start
sleep 10

# Verify restore
curl http://localhost:8001/health
curl http://localhost:8001/documents | jq '.total'

echo "✅ Restore complete"
```

### Partial Restore (ChromaDB Only)

```bash
# Stop services
docker-compose down

# Restore just the database
docker run --rm \
  -v rag_chroma_data:/data \
  -v $(pwd)/backups/2025-10-07:/backup \
  alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/chromadb-backup.tar.gz -C /data"

# Restart
docker-compose up -d
```

---

## Automated Backup Schedule

### Using Cron (Linux/Mac)

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /path/to/rag-provider && ./scripts/backup.sh >> /var/log/rag-backup.log 2>&1

# Add weekly cloud sync (Sunday 3 AM)
0 3 * * 0 cd /path/to/rag-provider && ./scripts/sync-to-cloud.sh >> /var/log/rag-cloud-sync.log 2>&1
```

### Using systemd Timer (Linux)

Create `/etc/systemd/system/rag-backup.service`:

```ini
[Unit]
Description=RAG System Backup
After=docker.service

[Service]
Type=oneshot
User=your-user
WorkingDirectory=/path/to/rag-provider
ExecStart=/path/to/rag-provider/scripts/backup.sh
```

Create `/etc/systemd/system/rag-backup.timer`:

```ini
[Unit]
Description=RAG Backup Timer
Requires=rag-backup.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl enable rag-backup.timer
sudo systemctl start rag-backup.timer
sudo systemctl list-timers --all
```

---

## Disaster Recovery Checklist

### If Data is Lost:

1. **Stop services immediately**
   ```bash
   docker-compose down
   ```

2. **Identify latest backup**
   ```bash
   ls -lh backups/
   ```

3. **Verify backup integrity**
   ```bash
   tar tzf backups/2025-10-07/chromadb-backup.tar.gz | head
   ```

4. **Restore from backup** (see Full Restore above)

5. **Verify data integrity**
   ```bash
   # Check document count
   curl http://localhost:8001/documents | jq '.total'

   # Test search
   curl -X POST http://localhost:8001/search \
     -H "Content-Type: application/json" \
     -d '{"text": "test", "top_k": 5}'
   ```

### If Backup is Corrupted:

1. **Try previous backup**
   ```bash
   ls -lt backups/ | head -5
   ```

2. **Check cloud backup** (if configured)
   ```bash
   aws s3 ls s3://your-bucket/rag-backups/
   ```

3. **Manual recovery** (if Obsidian files exist)
   - Documents can be re-ingested from Obsidian vault
   - Slower but preserves content

---

## Backup Verification

### Test Backup Script

```bash
# Create test backup
./scripts/backup.sh

# List contents
tar tzf backups/$(date +%Y-%m-%d)/chromadb-backup.tar.gz | head -20

# Check size
du -sh backups/$(date +%Y-%m-%d)/*
```

### Monthly Restore Test

```bash
# Test restore in separate environment
docker volume create rag_test_restore

# Restore to test volume
docker run --rm \
  -v rag_test_restore:/data \
  -v $(pwd)/backups/2025-10-07:/backup \
  alpine \
  tar xzf /backup/chromadb-backup.tar.gz -C /data

# Verify
docker run --rm -v rag_test_restore:/data alpine ls -lh /data

# Clean up
docker volume rm rag_test_restore
```

---

## Migration to New Server

### Export from Old Server

```bash
# On old server
./scripts/backup.sh

# Copy to new server
scp -r backups/$(date +%Y-%m-%d) user@new-server:/path/to/rag-provider/backups/
```

### Import on New Server

```bash
# On new server
cd /path/to/rag-provider

# Clone repository
git clone https://github.com/yourusername/rag-provider.git .

# Create environment
cp backups/2025-10-07/.env .

# Initialize Docker
docker-compose down
docker volume create rag_chroma_data

# Restore data
docker run --rm \
  -v rag_chroma_data:/data \
  -v $(pwd)/backups/2025-10-07:/backup \
  alpine \
  tar xzf /backup/chromadb-backup.tar.gz -C /data

# Start services
docker-compose up -d

# Verify
curl http://localhost:8001/health
```

---

## Storage Estimates

### Disk Space Planning

**Per 1,000 documents:**
- ChromaDB: ~100MB (varies by document size)
- Obsidian vault: ~1MB
- Total: ~101MB

**Backup retention:**
- Daily for 30 days: ~3GB (1000 docs)
- Weekly for 1 year: ~5GB (1000 docs)

**Recommendation:**
- Daily backups: 30 days
- Weekly backups: 1 year
- Monthly backups: indefinite (archive)

---

## Troubleshooting

### Backup Fails: "Permission Denied"

```bash
# Fix Docker volume permissions
docker run --rm -v rag_chroma_data:/data alpine chmod -R 777 /data
```

### Backup Size Too Large

```bash
# Check what's using space
docker exec rag_chromadb du -sh /chroma/chroma/*

# Consider compression
tar czf backup.tar.gz --use-compress-program="gzip -9" /data
```

### Restore Fails: "Cannot Overwrite"

```bash
# Force remove old data
docker volume rm -f rag_chroma_data
docker volume create rag_chroma_data
```

---

## Best Practices

1. **Test restores monthly** - Don't trust untested backups
2. **Keep 3-2-1 rule** - 3 copies, 2 media types, 1 offsite
3. **Monitor backup size** - Alert if growing unexpectedly
4. **Encrypt sensitive backups** - Use GPG for cloud storage
5. **Document restore procedures** - Train team on process
6. **Version control configs** - Git for .env and vocabulary/

---

## Quick Reference

### Daily Backup Command
```bash
./scripts/backup.sh
```

### Quick Restore Command
```bash
BACKUP_DATE="2025-10-07"
docker-compose down
docker run --rm -v rag_chroma_data:/data -v $(pwd)/backups/${BACKUP_DATE}:/backup alpine tar xzf /backup/chromadb-backup.tar.gz -C /data
docker-compose up -d
```

### Verify Backup
```bash
tar tzf backups/$(date +%Y-%m-%d)/chromadb-backup.tar.gz | wc -l
```

### Check Backup Size
```bash
du -sh backups/$(date +%Y-%m-%d)/
```

---

## Support

For issues:
1. Check Docker logs: `docker-compose logs -f`
2. Verify volume exists: `docker volume ls | grep chroma`
3. Test backup integrity: `tar tzf backup.tar.gz`
4. Contact support with backup date and error message

---

*Backup guide created: October 7, 2025*
*Version: 1.0*

# Port Configuration Guide

## Default Ports

| Service | Port | Environment Variable | Configurable |
|---------|------|---------------------|--------------|
| **RAG Service** | 8001 | `APP_PORT` | ✅ Yes |
| **ChromaDB** | 8000 | `CHROMA_PORT` | ✅ Yes |

## How to Change Ports

### Option 1: Environment Variables (Recommended)

**.env file:**
```bash
# RAG Service port
APP_PORT=8001
APP_HOST=0.0.0.0

# ChromaDB port
CHROMA_PORT=8000
CHROMA_HOST=localhost
```

**Then restart:**
```bash
docker-compose down
docker-compose up -d
```

**Or set at runtime:**
```bash
export APP_PORT=9001
docker-compose up -d
```

### Option 2: Docker Compose Override

**Create `docker-compose.override.yml`:**
```yaml
services:
  rag-service:
    ports:
      - "9001:9001"  # Change to your preferred port
    environment:
      - APP_PORT=9001

  chromadb:
    ports:
      - "9000:8000"  # External:Internal
```

### Option 3: Command Line

```bash
APP_PORT=9001 CHROMA_PORT=9000 docker-compose up -d
```

## Port Conflict Handling

### Automatic Port Selection

The RAG service now **automatically finds an available port** if the configured port is in use:

```python
# If APP_PORT=8001 is busy, tries:
# 8002, 8003, 8004, ... 8010
```

**Implementation:** The service uses socket binding to check port availability before startup. This happens in `app.py` (lines 1505-1536) and works both in Docker and local environments.

**Logs will show:**
```
⚠️  Port 8001 is already in use, trying alternative ports...
✅ Using alternative port 8002
🚀 Starting RAG service on 0.0.0.0:8002
```

**Note:** The Dockerfile now uses `python app.py` instead of `uvicorn` directly, which enables this automatic port detection feature.

### Manual Port Check

Check if ports are available:

```bash
# Check if port 8001 is in use
lsof -i :8001

# Check if port 8000 is in use
lsof -i :8000

# Kill process using port (if needed)
kill -9 $(lsof -t -i:8001)
```

## Port Requirements

### Minimum Requirements

1. **RAG Service** needs 1 port (default: 8001)
2. **ChromaDB** needs 1 port (default: 8000)

### Port Range Recommendations

**Development (Local):**
- RAG: 8001
- ChromaDB: 8000

**Production:**
- RAG: 80 or 443 (behind reverse proxy)
- ChromaDB: 8000 (internal only, not exposed)

**Multiple Instances:**
- Instance 1: RAG=8001, ChromaDB=8000
- Instance 2: RAG=8002, ChromaDB=8010
- Instance 3: RAG=8003, ChromaDB=8020

## Firewall Configuration

### Development (Allow All)
```bash
# macOS
sudo pfctl -d  # Disable firewall temporarily

# Linux (UFW)
sudo ufw allow 8000
sudo ufw allow 8001
```

### Production (Restrictive)
```bash
# Only allow RAG service externally
sudo ufw allow 8001/tcp

# Block ChromaDB from external access
sudo ufw deny 8000/tcp

# Allow ChromaDB only from localhost
iptables -A INPUT -p tcp --dport 8000 -s 127.0.0.1 -j ACCEPT
iptables -A INPUT -p tcp --dport 8000 -j DROP
```

## Reverse Proxy Setup

### Nginx (Recommended for Production)

```nginx
# /etc/nginx/sites-available/rag-provider
server {
    listen 80;
    server_name rag.yourdomain.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Then:**
```bash
sudo ln -s /etc/nginx/sites-available/rag-provider /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Caddy (Simpler)

```caddy
# Caddyfile
rag.yourdomain.com {
    reverse_proxy localhost:8001
}
```

### Traefik (Docker)

```yaml
# docker-compose.yml
services:
  rag-service:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.rag.rule=Host(`rag.yourdomain.com`)"
      - "traefik.http.services.rag.loadbalancer.server.port=8001"
```

## Health Check Endpoints

### Check if Services are Running

**RAG Service:**
```bash
curl http://localhost:8001/health

# Expected response:
{
  "status": "healthy",
  "chromadb": "connected",
  "llm_providers": {...}
}
```

**ChromaDB:**
```bash
curl http://localhost:8000/api/v1/heartbeat

# Expected response:
{"nanosecond heartbeat": 1234567890}
```

## Common Port Issues

### Issue 1: Port Already in Use

**Error:**
```
OSError: [Errno 48] Address already in use
```

**Solution:**
```bash
# Find what's using the port
lsof -i :8001

# Kill the process
kill -9 <PID>

# Or use different port
APP_PORT=8002 docker-compose up -d
```

### Issue 2: Permission Denied (Ports < 1024)

**Error:**
```
PermissionError: [Errno 13] Permission denied
```

**Solution:**
```bash
# Don't use ports < 1024 without root
APP_PORT=8001  # ✅ OK
APP_PORT=80    # ❌ Needs root

# Or use sudo (not recommended)
sudo docker-compose up -d
```

### Issue 3: Docker Port Mapping Fails

**Error:**
```
Error starting userland proxy: listen tcp4 0.0.0.0:8001: bind: address already in use
```

**Solution:**
```bash
# Stop all containers
docker-compose down

# Check what's using the port
docker ps -a | grep 8001

# Remove conflicting containers
docker rm -f $(docker ps -aq)

# Restart
docker-compose up -d
```

## Testing Port Configuration

### Verify Ports After Startup

```bash
# Check if services are listening
netstat -an | grep LISTEN | grep -E "8000|8001"

# Expected output:
tcp46      0      0  *.8001                 *.*                    LISTEN
tcp46      0      0  *.8000                 *.*                    LISTEN
```

### Test Connectivity

```bash
# Test RAG service
curl http://localhost:8001/health

# Test ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# Test from external network
curl http://YOUR_SERVER_IP:8001/health
```

## Environment-Specific Configurations

### Development (.env)
```bash
APP_HOST=0.0.0.0  # Accept connections from anywhere
APP_PORT=8001
CHROMA_HOST=localhost
CHROMA_PORT=8000
```

### Docker (.env)
```bash
APP_HOST=0.0.0.0
APP_PORT=8001
CHROMA_HOST=chromadb  # Use container name
CHROMA_PORT=8000
```

### Production (.env)
```bash
APP_HOST=127.0.0.1  # Only localhost (behind reverse proxy)
APP_PORT=8001
CHROMA_HOST=localhost
CHROMA_PORT=8000
```

## Troubleshooting

### Port Not Responding

1. **Check if service is running:**
   ```bash
   docker-compose ps
   ```

2. **Check logs:**
   ```bash
   docker-compose logs rag-service | grep "Starting RAG service"
   ```

3. **Verify port binding:**
   ```bash
   docker port rag_service
   ```

4. **Test inside container:**
   ```bash
   docker exec rag_service curl localhost:8001/health
   ```

### Port Conflicts Between Instances

Running multiple instances? Use different port ranges:

```bash
# Instance 1
APP_PORT=8001 CHROMA_PORT=8000 docker-compose up -d

# Instance 2
APP_PORT=8101 CHROMA_PORT=8100 docker-compose -p rag2 up -d

# Instance 3
APP_PORT=8201 CHROMA_PORT=8200 docker-compose -p rag3 up -d
```

## Summary

**Key Features:**
- ✅ Configurable ports via environment variables
- ✅ Automatic port conflict detection
- ✅ Automatic fallback to alternative ports
- ✅ Clear logging of port selection
- ✅ Works in Docker and local environments

**Best Practices:**
- Use environment variables for configuration
- Don't use ports < 1024 in development
- Use reverse proxy for production
- Keep ChromaDB internal (not externally accessible)
- Document custom port configurations

**Quick Start:**
```bash
# Default ports (8001, 8000)
docker-compose up -d

# Custom ports
APP_PORT=9001 CHROMA_PORT=9000 docker-compose up -d

# Check it worked
curl http://localhost:9001/health
```

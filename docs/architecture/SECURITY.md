# Security Guide

## Overview

The RAG Provider has been hardened with multiple security layers to protect against common vulnerabilities and ensure safe production deployment.

## Authentication

### API Key Authentication

All protected endpoints require authentication via API key:

```bash
# Set your API key
export RAG_API_KEY="your-secure-api-key-here"

# Or in .env file
RAG_API_KEY=your-secure-api-key-here
```

### API Key Usage

Include the API key in requests using one of these methods:

**Bearer Token (Recommended):**
```bash
curl -H "Authorization: Bearer your-api-key" http://localhost/api/ingest
```

**X-API-Key Header:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost/api/ingest
```

**Query Parameter (Not recommended for production):**
```bash
curl "http://localhost/api/ingest?api_key=your-api-key"
```

## CORS Configuration

CORS is configured securely with specific allowed origins:

```env
# Configure allowed origins (comma-separated)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080,https://yourdomain.com
```

## Protected Endpoints

The following endpoints require authentication:
- `/ingest` - Document ingestion
- `/ingest/file` - File upload
- `/ingest/batch` - Batch processing
- `/test-llm` - LLM testing
- `/admin/*` - Administrative functions

## Public Endpoints

These endpoints are publicly accessible:
- `/health` - Health check
- `/docs` - API documentation
- `/redoc` - Alternative API docs
- `/openapi.json` - OpenAPI specification

## Environment Variables

### Required Security Settings

```env
# Authentication
RAG_API_KEY=your-secure-api-key-here
REQUIRE_AUTH=true

# CORS
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
```

### Generating Secure API Keys

```bash
# Generate a secure random API key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Or using openssl
openssl rand -base64 32
```

## Security Features

### 1. Input Validation
- All inputs validated using Pydantic models
- File size limits enforced
- Content type validation

### 2. Error Handling
- Sanitized error messages
- No sensitive information in responses
- Structured error format

### 3. Resource Limits
- Docker container resource limits
- File size restrictions
- Temporary file cleanup

### 4. Network Security
- Nginx reverse proxy with security headers
- Debug routes removed from production
- Rate limiting ready (via nginx)

## Security Headers

The following security headers are automatically added:

```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

## Production Checklist

Before deploying to production:

- [ ] Set secure `RAG_API_KEY`
- [ ] Configure `ALLOWED_ORIGINS` for your domain
- [ ] Set `REQUIRE_AUTH=true`
- [ ] Remove any debug routes
- [ ] Configure HTTPS/SSL certificates
- [ ] Set up proper logging
- [ ] Configure monitoring
- [ ] Test authentication flows

## Vulnerability Reporting

If you discover a security vulnerability, please:

1. Do NOT open a public issue
2. Email security@yourorganization.com
3. Include detailed reproduction steps
4. Allow time for patching before disclosure

## Security Updates

Keep the following dependencies updated:
- FastAPI
- Pydantic
- All Python dependencies
- Docker base images
- Nginx

## Monitoring

Monitor these security metrics:
- Failed authentication attempts
- Unusual API usage patterns
- Resource consumption
- Error rates
- File upload patterns
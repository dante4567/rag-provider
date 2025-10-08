# Document Ingestion Guide - Easy Ways to Add Documents

## Quick Start (3 Methods)

### Method 1: Command Line (Fastest)
```bash
# Single file
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@/path/to/document.pdf" \
  -F "generate_obsidian=true"

# Batch upload
for file in ~/Documents/*.pdf; do
  echo "Uploading: $(basename $file)"
  curl -X POST http://localhost:8001/ingest/file \
    -F "file=@$file" \
    -F "generate_obsidian=true"
done
```

### Method 2: Web UI (Most User-Friendly)
```bash
cd web-ui
python app.py
# Open http://localhost:7860
# Drag & drop files
```

### Method 3: Telegram Bot (Mobile Upload)
```bash
export TELEGRAM_BOT_TOKEN="your_token"
cd telegram-bot
python rag_bot.py
# Send documents via Telegram chat
```

---

## Supported Formats

### Documents
- **PDFs**: ✅ Full OCR support
- **Markdown**: ✅ `.md` files with frontmatter
- **Text**: ✅ `.txt` files
- **Word**: ✅ `.docx` files
- **HTML**: ✅ `.html` files
- **Images**: ✅ `.png`, `.jpg` (OCR extraction)

### Email & Chat
- **Email**: ✅ `.eml` files (threading support)
- **WhatsApp**: ✅ Chat exports

---

## Advanced Upload Options

### With Metadata
```bash
curl -X POST http://localhost:8001/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Document content here",
    "filename": "my-document.md",
    "document_type": "text",
    "generate_obsidian": true,
    "metadata": {
      "projects": ["school-2026"],
      "topics": ["education/school/enrollment"]
    }
  }'
```

### With OCR
```bash
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@scanned-doc.pdf" \
  -F "process_ocr=true" \
  -F "generate_obsidian=true"
```

### Batch Upload with Error Handling
```bash
#!/bin/bash
SUCCESS=0
FAILED=0

for file in ~/Documents/**/*.{pdf,md,txt}; do
  echo "Processing: $file"

  response=$(curl -s -X POST http://localhost:8001/ingest/file \
    -F "file=@$file" \
    -F "generate_obsidian=true")

  success=$(echo "$response" | jq -r '.success')

  if [ "$success" = "true" ]; then
    SUCCESS=$((SUCCESS + 1))
    doc_id=$(echo "$response" | jq -r '.doc_id')
    chunks=$(echo "$response" | jq -r '.chunks')
    echo "  ✓ Success: $chunks chunks, ID: ${doc_id:0:8}"
  else
    FAILED=$((FAILED + 1))
    echo "  ✗ Failed"
  fi
done

echo ""
echo "=== Summary ==="
echo "Success: $SUCCESS"
echo "Failed: $FAILED"
```

---

## Directory Watching (Auto-Ingestion)

### Setup Auto-Ingestion
```bash
# Enable file watching in .env
ENABLE_FILE_WATCH=true
INPUT_PATH=/data/input
```

### How It Works
1. Drop files in `/data/input`
2. Service automatically detects and ingests them
3. Files moved to `/data/processed` after success
4. Obsidian files auto-created in `/data/obsidian`

### Docker Volume Mount
```yaml
# docker-compose.yml
services:
  rag-service:
    volumes:
      - ./input:/data/input           # Drop files here
      - ./processed:/data/processed   # Processed files
      - ./obsidian:/data/obsidian     # Obsidian vault
```

### Watch Directory Script
```bash
#!/bin/bash
# watch_and_upload.sh

WATCH_DIR="$HOME/Documents/to-ingest"
mkdir -p "$WATCH_DIR"

while true; do
  for file in "$WATCH_DIR"/*; do
    if [ -f "$file" ]; then
      echo "Found: $(basename $file)"

      curl -s -X POST http://localhost:8001/ingest/file \
        -F "file=@$file" \
        -F "generate_obsidian=true" | jq '{success, doc_id, chunks}'

      # Move to processed
      mv "$file" "$WATCH_DIR/../processed/"
    fi
  done

  sleep 10  # Check every 10 seconds
done
```

---

## Integration with Other Tools

### Alfred Workflow (macOS)
```applescript
-- Save as Alfred workflow
on alfred_script(q)
  set filePath to q
  do shell script "curl -X POST http://localhost:8001/ingest/file -F \"file=@" & filePath & "\" -F \"generate_obsidian=true\""
end alfred_script
```

### Hazel Rule (macOS)
```
If all of the following conditions are met:
  Name ends with .pdf

Do the following:
  Run shell script:
    curl -X POST http://localhost:8001/ingest/file \
      -F "file=@$1" \
      -F "generate_obsidian=true"
```

### Automator (macOS)
```bash
# Service: "Ingest to RAG"
for f in "$@"; do
  curl -X POST http://localhost:8001/ingest/file \
    -F "file=@$f" \
    -F "generate_obsidian=true"
done

osascript -e 'display notification "Documents ingested" with title "RAG Provider"'
```

### Keyboard Maestro
```
Trigger: Hot Key ⌘⌥I
Action: Execute Shell Script
  curl -X POST http://localhost:8001/ingest/file \
    -F "file=@$KMVAR_FilePath" \
    -F "generate_obsidian=true"
```

---

## Obsidian Integration

### Quick Add Plugin
```javascript
// Obsidian QuickAdd script
module.exports = async (params) => {
  const { quickAddApi, app } = params;

  const file = await quickAddApi.utility.selectFile();
  if (!file) return;

  const response = await fetch('http://localhost:8001/ingest/file', {
    method: 'POST',
    body: (() => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('generate_obsidian', 'true');
      return formData;
    })()
  });

  const result = await response.json();
  new Notice(`Ingested: ${result.chunks} chunks`);
};
```

### Templater Script
```javascript
<%*
// Add to daily note template
const file = await tp.system.suggester(
  (file) => file.name,
  app.vault.getFiles()
);

if (file) {
  const blob = await app.vault.readBinary(file);
  const formData = new FormData();
  formData.append('file', new Blob([blob]), file.name);
  formData.append('generate_obsidian', 'true');

  const response = await fetch('http://localhost:8001/ingest/file', {
    method: 'POST',
    body: formData
  });

  const result = await response.json();
  tR += `Ingested ${file.name}: ${result.chunks} chunks`;
}
%>
```

---

## Email Integration

### Gmail to RAG (via API)
```python
# gmail_to_rag.py
import base64
from googleapiclient.discovery import build
import requests

def ingest_gmail_thread(thread_id):
    service = build('gmail', 'v1', credentials=creds)
    thread = service.users().threads().get(userId='me', id=thread_id).execute()

    messages = []
    for msg in thread['messages']:
        payload = msg['payload']
        headers = {h['name']: h['value'] for h in payload['headers']}
        body = get_body(payload)

        messages.append({
            'from': headers.get('From'),
            'to': headers.get('To'),
            'date': headers.get('Date'),
            'subject': headers.get('Subject'),
            'body': body
        })

    # Send to RAG
    response = requests.post('http://localhost:8001/ingest', json={
        'content': format_email_thread(messages),
        'filename': f'email_thread_{thread_id}.md',
        'document_type': 'email',
        'generate_obsidian': True
    })

    return response.json()
```

### Thunderbird Integration
```bash
# Save emails as .eml, then ingest
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@email.eml" \
  -F "generate_obsidian=true"
```

---

## Mobile Ingestion

### iOS Shortcuts
```
Shortcut: "Add to RAG"

1. Get File from Input
2. Set Variable: File
3. Get Contents of URL
   - URL: http://your-server:8001/ingest/file
   - Method: POST
   - Request Body: Form
     - file: [File]
     - generate_obsidian: true
4. Show Notification: "Ingested to RAG"
```

### Android (Tasker)
```
Profile: New File in Documents
Event: File Modified
  Path: /sdcard/Documents/to-ingest/*

Task: Ingest to RAG
1. HTTP Request
   - Server: http://your-server:8001/ingest/file
   - Method: POST
   - File Upload: %evtprm1
   - Form Data: generate_obsidian=true
2. Notify: "Document ingested"
```

---

## Python SDK

### Simple Ingestion
```python
import requests
from pathlib import Path

def ingest_document(file_path: Path):
    with open(file_path, 'rb') as f:
        response = requests.post(
            'http://localhost:8001/ingest/file',
            files={'file': f},
            data={'generate_obsidian': 'true'}
        )
    return response.json()

# Usage
result = ingest_document(Path('document.pdf'))
print(f"Ingested: {result['chunks']} chunks, ID: {result['doc_id']}")
```

### Bulk Ingestion
```python
from pathlib import Path
import requests
from concurrent.futures import ThreadPoolExecutor

def ingest_directory(directory: Path, max_workers: int = 5):
    files = list(directory.glob('**/*.{pdf,md,txt}'))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(ingest_document, f) for f in files]
        results = [f.result() for f in futures]

    return results

# Usage
results = ingest_directory(Path('~/Documents/papers'))
print(f"Ingested {len(results)} documents")
```

---

## Best Practices

### 1. File Naming
- ✅ Use descriptive names: `2025-10-08-court-decision-custody.pdf`
- ✅ Include dates: `YYYY-MM-DD-topic.pdf`
- ❌ Avoid: `document.pdf`, `untitled.md`

### 2. Batch Uploads
- Upload in batches of 10-50 files
- Monitor enrichment costs
- Check for failed uploads

### 3. Obsidian Output
- Verify entity stubs created: `data/obsidian/refs/`
- Check frontmatter for dates, numbers, topics
- Validate wiki links work

### 4. Error Handling
- Always check `response.json()['success']`
- Retry failed uploads after checking logs
- Monitor disk space (Obsidian files grow)

---

## Troubleshooting

### Upload Fails
```bash
# Check service health
curl http://localhost:8001/health

# Check logs
docker-compose logs -f rag-service

# Verify file format
file document.pdf
```

### Slow Ingestion
- Large PDFs (>50 pages): 10-30s per document
- OCR processing: +5-10s per document
- Reduce batch size or use async uploads

### Missing Obsidian Files
```bash
# Check Obsidian path
ls -la data/obsidian/

# Verify generate_obsidian flag
curl -X POST http://localhost:8001/ingest/file \
  -F "file=@doc.pdf" \
  -F "generate_obsidian=true"  # ← Must be true
```

---

## Next Steps

1. **Try batch upload** - Use script from "Batch Upload with Error Handling"
2. **Set up directory watching** - Auto-ingest from `/data/input`
3. **Integrate with Obsidian** - Use QuickAdd or Templater scripts
4. **Mobile workflow** - Set up iOS Shortcut or Android Tasker

See `FRONTEND_INTEGRATION_GUIDE.md` for OpenWebUI and other frontend setups.

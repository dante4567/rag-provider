#!/bin/bash
# Automated RAG Testing Script
# This script helps you test the RAG service with real documents

set -e

echo "🧪 RAG Provider - Automated Testing Script"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if service is running
echo "1. Checking if RAG service is running..."
if curl -s http://localhost:8001/health > /dev/null; then
    echo -e "${GREEN}✅ Service is healthy${NC}"
else
    echo -e "${RED}❌ Service not running. Start with: docker-compose up -d${NC}"
    exit 1
fi

# Check for test documents directory
TEST_DOCS_DIR="./test_documents"
if [ ! -d "$TEST_DOCS_DIR" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  No test_documents/ directory found${NC}"
    echo "Creating test_documents/ directory..."
    mkdir -p "$TEST_DOCS_DIR"
    echo ""
    echo "📝 Please add some test documents to: $TEST_DOCS_DIR"
    echo "   Supported formats: PDF, TXT, MD, DOCX, DOC, EML"
    echo ""
    echo "Then run this script again."
    exit 0
fi

# Count documents
DOC_COUNT=$(find "$TEST_DOCS_DIR" -type f \( -name "*.pdf" -o -name "*.txt" -o -name "*.md" -o -name "*.docx" -o -name "*.doc" -o -name "*.eml" \) | wc -l)

if [ "$DOC_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No documents found in $TEST_DOCS_DIR${NC}"
    echo "Add some test documents and run again."
    exit 0
fi

echo ""
echo "📚 Found $DOC_COUNT documents to test"
echo ""

# Upload documents
echo "2. Uploading documents..."
UPLOAD_COUNT=0
FAILED_COUNT=0

for file in "$TEST_DOCS_DIR"/*; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        echo -n "   Uploading: $filename ... "

        # Upload with curl
        response=$(curl -s -X POST -F "file=@$file" http://localhost:8001/ingest/file)

        # Check if successful
        if echo "$response" | grep -q '"success":true'; then
            echo -e "${GREEN}✅${NC}"
            UPLOAD_COUNT=$((UPLOAD_COUNT + 1))
        else
            echo -e "${RED}❌${NC}"
            FAILED_COUNT=$((FAILED_COUNT + 1))
            echo "      Error: $response"
        fi
    fi
done

echo ""
echo "📊 Upload Results:"
echo "   ✅ Successful: $UPLOAD_COUNT"
echo "   ❌ Failed: $FAILED_COUNT"
echo ""

# Test search
echo "3. Testing search..."
echo -n "   Searching for 'AI' ... "
search_response=$(curl -s -X POST http://localhost:8001/search \
    -H "Content-Type: application/json" \
    -d '{"text": "AI", "top_k": 3}')

result_count=$(echo "$search_response" | grep -o '"content"' | wc -l)
echo -e "${GREEN}Found $result_count results${NC}"

# Test chat
echo ""
echo "4. Testing chat..."
echo -n "   Asking 'What topics are covered in these documents?' ... "
chat_response=$(curl -s -X POST http://localhost:8001/chat \
    -H "Content-Type: application/json" \
    -d '{"question": "What topics are covered in these documents?", "llm_model": "groq/llama-3.1-8b-instant"}')

if echo "$chat_response" | grep -q '"answer"'; then
    echo -e "${GREEN}✅ Got response${NC}"
    echo ""
    echo "   Answer preview:"
    echo "$chat_response" | grep -o '"answer":"[^"]*"' | head -c 200
    echo "..."
else
    echo -e "${RED}❌ Failed${NC}"
fi

# Get stats
echo ""
echo "5. Service Statistics:"
stats=$(curl -s http://localhost:8001/stats)
echo "$stats" | python3 -m json.tool 2>/dev/null || echo "$stats"

echo ""
echo -e "${GREEN}🎉 Testing Complete!${NC}"
echo ""
echo "📝 Next steps:"
echo "   1. Check Obsidian exports: docker exec rag_service ls /app/data/obsidian_export/"
echo "   2. Review tag learning in Statistics tab of Web UI"
echo "   3. Test with more documents"
echo ""

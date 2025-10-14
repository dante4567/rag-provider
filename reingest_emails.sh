#!/bin/bash
#
# Re-ingest all emails with correct date extraction
#

EMAIL_DIR="/Users/danielteckentrup/Documents/villa-luna"
API_URL="http://localhost:8001"
LOG_FILE="reingest_$(date +%Y%m%d_%H%M%S).log"

echo "🔄 Starting email re-ingestion from $EMAIL_DIR"
echo "📝 Logging to: $LOG_FILE"
echo ""

total=$(ls "$EMAIL_DIR"/*.eml 2>/dev/null | wc -l)
count=0
success=0
failed=0

for file in "$EMAIL_DIR"/*.eml; do
    count=$((count + 1))
    filename=$(basename "$file")

    echo -n "[$count/$total] Ingesting: $filename... "

    response=$(curl -s -X POST "$API_URL/ingest/file" \
        -F "file=@$file" \
        -F "generate_obsidian=true" 2>&1)

    if echo "$response" | jq -e '.success' > /dev/null 2>&1; then
        obsidian_path=$(echo "$response" | jq -r '.obsidian_path')
        echo "✅ $(basename "$obsidian_path")"
        echo "[$count/$total] ✅ $filename → $obsidian_path" >> "$LOG_FILE"
        success=$((success + 1))
    else
        echo "❌ FAILED"
        echo "[$count/$total] ❌ $filename - Error: $response" >> "$LOG_FILE"
        failed=$((failed + 1))
    fi

    # Progress update every 50 files
    if [ $((count % 50)) -eq 0 ]; then
        echo ""
        echo "📊 Progress: $count/$total | Success: $success | Failed: $failed"
        echo ""
    fi

    # Delay to avoid rate limits (increased from 0.1s)
    sleep 0.5
done

echo ""
echo "✅ Re-ingestion complete!"
echo "   Total: $total"
echo "   Success: $success"
echo "   Failed: $failed"
echo "   Log: $LOG_FILE"

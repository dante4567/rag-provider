#!/bin/bash
#
# Resume email ingestion from where it stopped
#

EMAIL_DIR="/Users/danielteckentrup/Documents/villa-luna"
API_URL="http://localhost:8001"
LOG_FILE="resume_$(date +%Y%m%d_%H%M%S).log"
START_INDEX=127  # Start from email #127

echo "🔄 Resuming email ingestion from #$START_INDEX"
echo "📝 Logging to: $LOG_FILE"
echo ""

total=$(ls "$EMAIL_DIR"/*.eml 2>/dev/null | wc -l)
count=$START_INDEX
success=0
failed=0

# Process emails starting from START_INDEX
# Use process substitution to handle filenames with spaces correctly
while IFS= read -r file; do
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
        error_msg=$(echo "$response" | jq -c '.' 2>/dev/null || echo "$response")
        echo "[$count/$total] ❌ $filename - Error: $error_msg" >> "$LOG_FILE"
        failed=$((failed + 1))
    fi

    # Progress update every 50 files
    if [ $(((count - START_INDEX + 1) % 50)) -eq 0 ]; then
        echo ""
        echo "📊 Progress: $count/$total | Success: $success | Failed: $failed"
        echo ""
    fi

    # Delay to avoid rate limits (increased to 2s for reliability)
    sleep 2
done < <(ls "$EMAIL_DIR"/*.eml | tail -n +$START_INDEX)

echo ""
echo "✅ Resume complete!"
echo "   Processed: $((total - START_INDEX + 1))"
echo "   Success: $success"
echo "   Failed: $failed"
echo "   Log: $LOG_FILE"

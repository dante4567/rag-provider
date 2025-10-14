#!/bin/bash
#
# Retry failed emails from re-ingestion log
#

LOG_FILE="$1"
API_URL="http://localhost:8001"
EMAIL_DIR="/Users/danielteckentrup/Documents/villa-luna"

if [ -z "$LOG_FILE" ]; then
    echo "Usage: $0 <log_file>"
    echo "Example: $0 reingest_20251014_204205.log"
    exit 1
fi

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Log file not found: $LOG_FILE"
    exit 1
fi

# Extract failed filenames
failed_files=$(grep "❌" "$LOG_FILE" | awk '{print $3}')
failed_count=$(echo "$failed_files" | wc -l | tr -d ' ')

if [ "$failed_count" -eq 0 ]; then
    echo "✅ No failed files found in log"
    exit 0
fi

echo "🔄 Retrying $failed_count failed emails..."
echo ""

success=0
still_failed=0

for filename in $failed_files; do
    file_path="$EMAIL_DIR/$filename"

    if [ ! -f "$file_path" ]; then
        echo "⚠️  File not found: $filename"
        continue
    fi

    echo -n "Retrying: $filename... "

    response=$(curl -s -X POST "$API_URL/ingest/file" \
        -F "file=@$file_path" \
        -F "generate_obsidian=true" 2>&1)

    if echo "$response" | jq -e '.success' > /dev/null 2>&1; then
        obsidian_path=$(echo "$response" | jq -r '.obsidian_path')
        echo "✅ $(basename "$obsidian_path")"
        success=$((success + 1))
    else
        echo "❌ FAILED"
        still_failed=$((still_failed + 1))
    fi

    # Longer delay to avoid rate limits
    sleep 2
done

echo ""
echo "📊 Retry Results:"
echo "   Success: $success"
echo "   Still Failed: $still_failed"

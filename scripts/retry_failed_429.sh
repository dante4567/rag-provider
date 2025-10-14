#!/bin/bash
# Retry emails that failed with HTTP 429

LOG_FILE="${1:-ingest_log_villa_luna_20251014.txt}"

echo "🔄 Extracting failed emails from $LOG_FILE..."

# Extract failed email filenames
grep "❌ HTTP 429" "$LOG_FILE" | sed 's/.*Ingesting: \(.*\)\.eml.*/\1.eml/' > /tmp/failed_429.txt

failed_count=$(wc -l < /tmp/failed_429.txt)
echo "📊 Found $failed_count failed emails"

if [ "$failed_count" -eq 0 ]; then
    echo "✅ No failed emails to retry!"
    exit 0
fi

echo ""
echo "🔄 Retrying failed emails with 5-second delay..."
echo ""

BASE_URL="http://localhost:8001"
EMAIL_DIR="/Users/danielteckentrup/Documents/villa-luna"

successful=0
still_failed=0

while IFS= read -r filename; do
    email_path="$EMAIL_DIR/$filename"

    if [ ! -f "$email_path" ]; then
        echo "⚠️  File not found: $filename"
        continue
    fi

    echo -n "📧 Retrying: $filename... "

    response=$(curl -s -w "\n%{http_code}" -X POST \
        -F "file=@$email_path" \
        -F "generate_obsidian=true" \
        "$BASE_URL/ingest/file" 2>&1)

    http_code=$(echo "$response" | tail -1)

    if [ "$http_code" = "200" ]; then
        doc_id=$(echo "$response" | head -1 | jq -r '.doc_id' 2>/dev/null | cut -c1-8)
        echo "✅ $doc_id"
        ((successful++))
    else
        echo "❌ HTTP $http_code"
        ((still_failed++))
    fi

    sleep 5  # 5-second delay to avoid rate limits

done < /tmp/failed_429.txt

echo ""
echo "📊 Retry Summary:"
echo "   ✅ Successful: $successful"
echo "   ❌ Still failed: $still_failed"
echo "   📈 Success rate: $((successful * 100 / failed_count))%"

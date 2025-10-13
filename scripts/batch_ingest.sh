#!/bin/bash
# Batch ingest all ChatGPT JSON conversations
# Tracks progress and handles errors

LOG_FILE="ingest_log_$(date +%Y%m%d_%H%M%S).txt"
SUCCESS_COUNT=0
FAIL_COUNT=0
TOTAL=$(ls -1 *.json 2>/dev/null | wc -l | tr -d ' ')

echo "Starting batch ingestion: $TOTAL JSON files"
echo "Log file: $LOG_FILE"
echo ""

COUNTER=0

for file in *.json; do
    COUNTER=$((COUNTER + 1))

    # Progress indicator
    PERCENT=$((COUNTER * 100 / TOTAL))
    echo -ne "\r[$COUNTER/$TOTAL - ${PERCENT}%] Processing: ${file:0:50}..."

    # Attempt ingestion
    RESPONSE=$(curl -s -X POST http://localhost:8001/ingest/file -F "file=@$file" 2>&1)

    # Check if successful
    if echo "$RESPONSE" | grep -q '"success":true'; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo "[$COUNTER/$TOTAL] ✅ SUCCESS: $file" >> "$LOG_FILE"
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "[$COUNTER/$TOTAL] ❌ FAILED: $file" >> "$LOG_FILE"
        echo "  Error: $RESPONSE" >> "$LOG_FILE"
        echo ""
        echo "⚠️  Failed: $file (check log for details)"
    fi

    # Delay to respect rate limits (1 second per file)
    sleep 1
done

echo ""
echo ""
echo "=========================================="
echo "Batch Ingestion Complete!"
echo "=========================================="
echo "Total files:     $TOTAL"
echo "✅ Successful:   $SUCCESS_COUNT"
echo "❌ Failed:       $FAIL_COUNT"
echo "Success rate:    $((SUCCESS_COUNT * 100 / TOTAL))%"
echo ""
echo "Log file: $LOG_FILE"
echo "=========================================="

#!/bin/bash
# Retry failed ingestions from log file
# Usage: ./retry_failed.sh ingest_log_YYYYMMDD_HHMMSS.txt

if [ -z "$1" ]; then
    # Find most recent log
    LOG_FILE=$(ls -t ingest_log_*.txt 2>/dev/null | head -1)
    if [ -z "$LOG_FILE" ]; then
        echo "No log files found. Please specify log file as argument."
        exit 1
    fi
else
    LOG_FILE="$1"
fi

echo "Extracting failed files from: $LOG_FILE"

# Extract failed filenames
FAILED_FILES=$(grep "❌ FAILED:" "$LOG_FILE" | sed 's/.*FAILED: //' | sort | uniq)
FAIL_COUNT=$(echo "$FAILED_FILES" | wc -l | tr -d ' ')

if [ "$FAIL_COUNT" -eq 0 ]; then
    echo "No failed files found in log!"
    exit 0
fi

echo "Found $FAIL_COUNT failed files"
echo "Starting retry with 1-second delays..."
echo ""

SUCCESS=0
STILL_FAIL=0
RETRY_LOG="retry_$(date +%Y%m%d_%H%M%S).txt"

COUNTER=0
# Use while loop with IFS to handle filenames with spaces
while IFS= read -r file; do
    COUNTER=$((COUNTER + 1))
    echo -ne "\r[$COUNTER/$FAIL_COUNT] Retrying: ${file:0:50}..."

    # Change to input directory
    cd ../data/input || exit 1
    RESPONSE=$(curl -s -X POST http://localhost:8001/ingest/file -F "file=@$file" 2>&1)
    cd - > /dev/null || exit 1

    if echo "$RESPONSE" | grep -q '"success":true'; then
        SUCCESS=$((SUCCESS + 1))
        echo "✅ SUCCESS: $file" >> "$RETRY_LOG"
    else
        STILL_FAIL=$((STILL_FAIL + 1))
        echo "❌ STILL FAILED: $file" >> "$RETRY_LOG"
        echo "  Error: $RESPONSE" >> "$RETRY_LOG"
    fi

    sleep 1
done <<< "$FAILED_FILES"

echo ""
echo ""
echo "=========================================="
echo "Retry Complete!"
echo "=========================================="
echo "Attempted:       $FAIL_COUNT"
echo "✅ Now Success:  $SUCCESS"
echo "❌ Still Failed: $STILL_FAIL"
echo "Success rate:    $((SUCCESS * 100 / FAIL_COUNT))%"
echo ""
echo "Retry log: $RETRY_LOG"
echo "=========================================="

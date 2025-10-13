#!/bin/bash
#
# Batch Ingestion Test Script
# Ingests a representative sample of files for performance testing
#

set -e

API_URL="${API_URL:-http://localhost:8001}"
DATA_DIR="$(cd "$(dirname "$0")/.." && pwd)/data"

echo "================================================================================"
echo "BATCH INGESTION TEST"
echo "================================================================================"

# Check API health
echo ""
echo "🔍 Checking API health at $API_URL..."
if curl -sf "$API_URL/health" > /dev/null; then
    echo "✅ API is healthy"
else
    echo "❌ API health check failed"
    exit 1
fi

# Initialize counters
SUCCESS_COUNT=0
FAILURE_COUNT=0
START_TIME=$(date +%s)

# Function to ingest a file
ingest_file() {
    local FILE_PATH="$1"
    local FILE_NAME=$(basename "$FILE_PATH")
    local FILE_START=$(date +%s)

    if curl -sf -X POST "$API_URL/ingest/file" \
        -F "file=@$FILE_PATH" \
        -o /dev/null 2>&1; then
        FILE_END=$(date +%s)
        FILE_DURATION=$((FILE_END - FILE_START))
        echo "   ✅ $FILE_NAME (${FILE_DURATION}s)"
        # Sleep to avoid rate limits (Voyage: 3 RPM max on free tier)
        sleep 25
        return 0
    else
        FILE_END=$(date +%s)
        FILE_DURATION=$((FILE_END - FILE_START))
        echo "   ❌ $FILE_NAME (${FILE_DURATION}s) - FAILED"
        # Still sleep on failure to avoid hammering the API
        sleep 2
        return 1
    fi
}

# Ingest contacts (vCards)
echo ""
echo "📂 Ingesting contacts (vCards)..."
CONTACT_COUNT=0
for FILE in "$DATA_DIR"/contacts/*.vcf; do
    if [ -f "$FILE" ] && [ $CONTACT_COUNT -lt 5 ]; then
        if ingest_file "$FILE"; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            FAILURE_COUNT=$((FAILURE_COUNT + 1))
        fi
        CONTACT_COUNT=$((CONTACT_COUNT + 1))
    fi
done
echo "   ✓ Processed $CONTACT_COUNT contact files"

# Ingest calendar events (iCal)
echo ""
echo "📂 Ingesting calendar events (iCal)..."
CALENDAR_COUNT=0
for FILE in "$DATA_DIR"/calendar/*.ics; do
    if [ -f "$FILE" ] && [ $CALENDAR_COUNT -lt 5 ]; then
        if ingest_file "$FILE"; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            FAILURE_COUNT=$((FAILURE_COUNT + 1))
        fi
        CALENDAR_COUNT=$((CALENDAR_COUNT + 1))
    fi
done
echo "   ✓ Processed $CALENDAR_COUNT calendar files"

# Ingest PDFs
echo ""
echo "📂 Ingesting PDFs..."
PDF_COUNT=0
for FILE in "$DATA_DIR"/processed_originals/*.pdf; do
    if [ -f "$FILE" ] && [ $PDF_COUNT -lt 2 ]; then
        if ingest_file "$FILE"; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            FAILURE_COUNT=$((FAILURE_COUNT + 1))
        fi
        PDF_COUNT=$((PDF_COUNT + 1))
    fi
done
echo "   ✓ Processed $PDF_COUNT PDF files"

# Ingest markdown files
echo ""
echo "📂 Ingesting markdown files..."
MD_COUNT=0
for FILE in "$DATA_DIR"/obsidian/*.md; do
    if [ -f "$FILE" ] && [ $MD_COUNT -lt 5 ]; then
        if ingest_file "$FILE"; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            FAILURE_COUNT=$((FAILURE_COUNT + 1))
        fi
        MD_COUNT=$((MD_COUNT + 1))
    fi
done
echo "   ✓ Processed $MD_COUNT markdown files"

# Ingest input files
echo ""
echo "📂 Ingesting input directory files..."
INPUT_COUNT=0
for FILE in "$DATA_DIR"/input/*; do
    if [ -f "$FILE" ] && [ $INPUT_COUNT -lt 3 ]; then
        if ingest_file "$FILE"; then
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            FAILURE_COUNT=$((FAILURE_COUNT + 1))
        fi
        INPUT_COUNT=$((INPUT_COUNT + 1))
    fi
done
echo "   ✓ Processed $INPUT_COUNT input files"

# Calculate stats
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
TOTAL_FILES=$((SUCCESS_COUNT + FAILURE_COUNT))
SUCCESS_RATE=$((SUCCESS_COUNT * 100 / TOTAL_FILES))
AVG_DURATION=$((TOTAL_DURATION / TOTAL_FILES))

# Print results
echo ""
echo "================================================================================"
echo "INGESTION RESULTS"
echo "================================================================================"
echo ""
echo "📊 Overall Statistics:"
echo "   Total files:      $TOTAL_FILES"
echo "   ✅ Successes:     $SUCCESS_COUNT (${SUCCESS_RATE}%)"
echo "   ❌ Failures:      $FAILURE_COUNT"
echo "   ⏱️  Total time:    ${TOTAL_DURATION}s"
echo "   ⚡ Avg per file:   ${AVG_DURATION}s"

# Check final corpus size
echo ""
echo "🔍 Checking final corpus size..."
STATS=$(curl -sf "$API_URL/stats")
DOC_COUNT=$(echo "$STATS" | grep -o '"total_documents":[0-9]*' | grep -o '[0-9]*')
CHUNK_COUNT=$(echo "$STATS" | grep -o '"total_chunks":[0-9]*' | grep -o '[0-9]*')

if [ -n "$DOC_COUNT" ]; then
    echo "   📚 Total documents indexed: $DOC_COUNT"
    echo "   🧩 Total chunks:            $CHUNK_COUNT"
    if [ "$DOC_COUNT" -gt 0 ]; then
        AVG_CHUNKS=$((CHUNK_COUNT / DOC_COUNT))
        echo "   📊 Avg chunks per doc:      $AVG_CHUNKS"
    fi
fi

echo ""
echo "================================================================================"
echo "✅ BATCH INGESTION TEST COMPLETE"
echo "================================================================================"

# Exit with appropriate code
if [ $FAILURE_COUNT -eq 0 ]; then
    exit 0
else
    exit 1
fi

#!/bin/bash
# Monitor batch ingestion progress

TOTAL=5073
SUCCESS=$(grep -c "✅ success" ingest_progress.log 2>/dev/null || echo "0")
FAILED=$(grep -c "❌ HTTP" ingest_progress.log 2>/dev/null || echo "0")
SUCCESS=${SUCCESS//[^0-9]/}
FAILED=${FAILED//[^0-9]/}
PROGRESS=$((SUCCESS + FAILED))
if [ $TOTAL -gt 0 ]; then
    PERCENT=$((PROGRESS * 100 / TOTAL))
else
    PERCENT=0
fi

echo "📊 Batch Ingestion Progress"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Success:  $SUCCESS"
echo "❌ Failed:   $FAILED"
echo "📈 Progress: $PROGRESS / $TOTAL ($PERCENT%)"
echo ""

# Show last 5 lines
echo "🔍 Recent activity:"
tail -5 ingest_progress.log 2>/dev/null

# Estimate time remaining (1 second per file)
REMAINING=$((TOTAL - PROGRESS))
MINUTES=$((REMAINING / 60))
echo ""
echo "⏱️  Estimated time remaining: ~$MINUTES minutes"

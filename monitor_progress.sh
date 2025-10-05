#!/bin/bash
# Monitor upload progress

echo "🔍 Monitoring RAG service..."
echo "Press Ctrl+C to stop"
echo ""

while true; do
    clear
    echo "========================================="
    echo "📊 RAG SERVICE STATUS"
    echo "========================================="
    echo ""

    # Get stats
    curl -s http://localhost:8001/stats 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f'📊 Documents: {data[\"total_documents\"]}')
    print(f'📝 Chunks: {data[\"total_chunks\"]}')
    print(f'💾 Storage: {data[\"storage_used_mb\"]}MB')
    print(f'📈 Avg Chunks/Doc: {data[\"total_chunks\"]/max(data[\"total_documents\"],1):.1f}')
    last = data['last_ingestion'][:19] if 'last_ingestion' in data else 'N/A'
    print(f'⏰ Last Upload: {last}')
except Exception as e:
    print('⚠️  Service busy or not responding')
    print(f'   Error: {e}')
"

    echo ""
    echo "========================================="

    # Memory usage
    docker stats rag_service --no-stream --format "💾 Memory: {{.MemUsage}} ({{.MemPerc}})"

    echo "========================================="
    echo ""
    echo "Next update in 5 seconds..."
    sleep 5
done

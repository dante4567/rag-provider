#!/bin/bash
# Start Web UI with correct Python version

echo "🚀 Starting RAG Web UI..."

# Check if RAG service is running
echo "Checking RAG service..."
if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "⚠️  RAG service not running!"
    echo "Start it with: cd .. && docker-compose up -d"
    read -p "Press Enter to continue anyway or Ctrl+C to exit..."
fi

# Install dependencies if needed
if ! python3 -c "import gradio" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    python3 -m pip install -r requirements.txt
fi

echo "✅ Starting Web UI on http://localhost:7860"
echo ""

# Run with Python 3
python3 app.py

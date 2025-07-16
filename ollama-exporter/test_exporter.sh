#!/bin/bash

echo "Testing Ollama Exporter..."
echo

# Check if Ollama is accessible
echo "1. Testing Ollama API..."
curl -s http://localhost:11434/api/tags | jq . 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Ollama API is accessible"
else
    echo "✗ Cannot reach Ollama API at localhost:11434"
fi
echo

# Start the exporter in background
echo "2. Starting exporter..."
python3 ollama_exporter.py &
EXPORTER_PID=$!
sleep 5

# Check metrics endpoint
echo "3. Testing metrics endpoint..."
curl -s http://localhost:9200/metrics | grep "ollama_" | head -10
if [ $? -eq 0 ]; then
    echo "✓ Metrics are being exported"
else
    echo "✗ No metrics found"
fi

# Cleanup
kill $EXPORTER_PID 2>/dev/null
echo
echo "Test complete!"
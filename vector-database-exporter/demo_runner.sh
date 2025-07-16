#!/bin/bash

# Demo Runner for Vector Database Monitoring Stack
# This script demonstrates the complete vector database monitoring functionality

echo "=== Vector Database Monitoring Demo ==="
echo "Starting complete stack with real vector operations..."
echo

# Function to check if service is ready
check_service_ready() {
    local service_name=$1
    local port=$2
    local max_attempts=30
    local attempt=1
    
    echo "Checking if $service_name is ready on port $port..."
    while ! curl -s http://localhost:$port/health >/dev/null 2>&1 && [ $attempt -le $max_attempts ]; do
        echo "Attempt $attempt/$max_attempts: Waiting for $service_name..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        echo "❌ $service_name failed to start after $max_attempts attempts"
        return 1
    else
        echo "✅ $service_name is ready"
        return 0
    fi
}

# Start the main monitoring stack
echo "Starting main monitoring stack..."
cd ..
docker compose up -d prometheus grafana chromadb vector_db_exporter

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Check if ChromaDB is ready
echo "Checking ChromaDB availability..."
if curl -s http://localhost:8000/api/v1/heartbeat | grep -q '"nanosecond_heartbeat"'; then
    echo "✅ ChromaDB is ready"
else
    echo "❌ ChromaDB is not ready"
fi

# Check if Vector DB exporter is ready
echo "Checking Vector DB exporter..."
if curl -s http://localhost:9205/metrics | grep -q 'vector_db_'; then
    echo "✅ Vector DB exporter is ready and exposing metrics"
else
    echo "❌ Vector DB exporter is not ready"
fi

# Check if Prometheus is scraping vector DB metrics
echo "Checking Prometheus for vector DB metrics..."
if curl -s 'http://localhost:9090/api/v1/query?query=vector_db_embeddings_generated_total' | grep -q 'vector_db_embeddings_generated_total'; then
    echo "✅ Prometheus is scraping vector DB metrics"
else
    echo "❌ Prometheus is not scraping vector DB metrics yet"
fi

echo
echo "=== Starting Demo Application ==="
echo "The demo application will perform real vector operations:"
echo "1. Insert documents with embeddings into ChromaDB"
echo "2. Perform similarity searches"
echo "3. Generate metrics that will be collected by the exporter"
echo "4. Metrics will be scraped by Prometheus and displayed in Grafana"
echo

# Start the demo application
echo "Starting demo application..."
cd vector-database-exporter
python3 test_vector_operations.py &
DEMO_PID=$!

echo "Demo application started with PID: $DEMO_PID"
echo
echo "=== Monitoring URLs ==="
echo "Grafana Dashboard: http://localhost:3000/d/vector-database-monitoring"
echo "Prometheus Metrics: http://localhost:9090/graph"
echo "Vector DB Exporter: http://localhost:9205/metrics"
echo "ChromaDB API: http://localhost:8000"
echo
echo "=== Demo Instructions ==="
echo "1. Open Grafana at http://localhost:3000 (admin/admin)"
echo "2. Navigate to the Vector Database Monitoring dashboard"
echo "3. Watch the metrics update in real-time as the demo app runs"
echo "4. All panels should show data (not just one panel)"
echo "5. Press Ctrl+C to stop the demo"
echo
echo "Demo is now running. Press Ctrl+C to stop..."

# Wait for interrupt
trap "echo 'Stopping demo...'; kill $DEMO_PID 2>/dev/null; exit 0" INT
wait $DEMO_PID
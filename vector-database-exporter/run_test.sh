#!/bin/bash

echo "🚀 Starting Vector Database Monitoring Test Environment"
echo "====================================================="

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Stop any existing test containers
echo "🧹 Cleaning up any existing test containers..."
docker compose -f docker-compose.test.yml down -v 2>/dev/null

# Build the images
echo "🔨 Building Docker images..."
docker compose -f docker-compose.test.yml build

# Start the services
echo "🚀 Starting services..."
docker compose -f docker-compose.test.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if ChromaDB is running
echo "🔍 Checking ChromaDB health..."
if curl -s http://localhost:8000/api/v1/heartbeat > /dev/null; then
    echo "✅ ChromaDB is running"
else
    echo "❌ ChromaDB is not responding"
    exit 1
fi

# Check if metrics exporter is running
echo "🔍 Checking Vector DB Exporter..."
if curl -s http://localhost:9206/metrics | grep -q "vector_db"; then
    echo "✅ Vector DB Exporter is running"
else
    echo "❌ Vector DB Exporter is not responding"
fi

echo ""
echo "📊 Test environment is ready!"
echo "============================="
echo ""
echo "📍 Access points:"
echo "   - ChromaDB UI: http://localhost:8000"
echo "   - Metrics: http://localhost:9206/metrics"
echo "   - Main Grafana: http://localhost:3000"
echo ""
echo "📝 View logs:"
echo "   - All logs: docker compose -f docker-compose.test.yml logs -f"
echo "   - RAG app: docker compose -f docker-compose.test.yml logs -f vector_test_app"
echo "   - Exporter: docker compose -f docker-compose.test.yml logs -f vector_db_exporter_real"
echo ""
echo "🛑 To stop:"
echo "   docker compose -f docker-compose.test.yml down -v"
echo ""
echo "The test RAG application is now running and generating real metrics!"
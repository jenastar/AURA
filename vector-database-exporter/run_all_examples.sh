#!/bin/bash

echo "Running Vector Database Monitoring Examples"
echo "=========================================="

# Ensure ChromaDB is running
echo "Checking ChromaDB..."
if ! curl -s http://localhost:8000/api/v1/heartbeat > /dev/null; then
    echo "Starting ChromaDB..."
    docker compose -f chromadb-compose.yml up -d
    sleep 5
fi

# Ensure vector exporter is in real mode
echo "Configuring vector exporter for real mode..."
docker compose stop vector_db_exporter
DEMO_MODE=false docker compose up -d vector_db_exporter
sleep 5

# Run each example
echo -e "\n\nRunning Example 1: Document RAG System"
docker exec mon_vector_db_exporter python /app/example1_document_rag.py

echo -e "\n\nRunning Example 2: Image Search System"
docker exec mon_vector_db_exporter python /app/example2_image_search.py

echo -e "\n\nRunning Example 3: Multi-Modal Search"
docker exec mon_vector_db_exporter python /app/example3_multimodal_search.py

echo -e "\n\nRunning Example 4: Performance Testing"
docker exec mon_vector_db_exporter python /app/example4_performance_test.py

echo -e "\n\n✅ All examples completed!"
echo "View metrics in Grafana: http://localhost:3000"
echo "Dashboard: Vector Database Monitoring"
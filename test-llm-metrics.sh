#!/bin/bash

echo "Testing LLM Metrics Collection"
echo "=============================="

# Build the LLM metrics exporter
echo "Building LLM metrics exporter..."
docker compose build llm_metrics_exporter llm_inference_wrapper

# Start the services
echo "Starting services..."
docker compose up -d prometheus grafana llm_metrics_exporter llm_inference_wrapper

# Wait for services to start
echo "Waiting for services to start..."
sleep 10

# Deploy test Ollama if not already running
if ! docker ps | grep -q test_ollama; then
    echo "Starting Ollama test container..."
    docker run -d \
        --name test_ollama \
        --gpus all \
        -p 11434:11434 \
        --network aura_mon_network \
        --label project=test_llm \
        ollama/ollama:latest
    
    # Wait for Ollama to start
    sleep 5
    
    # Pull a model
    echo "Pulling llama2 model (this may take a while)..."
    docker exec test_ollama ollama pull llama2:7b
fi

# Test direct Ollama inference
echo "Testing direct Ollama inference..."
curl -X POST http://localhost:11434/api/generate \
    -H "Content-Type: application/json" \
    -d '{
        "model": "llama2:7b",
        "prompt": "Why is the sky blue? Answer in one sentence.",
        "stream": false
    }' &

# Wait a bit
sleep 2

# Test through the wrapper (with metrics)
echo -e "\n\nTesting inference through wrapper (with metrics)..."
curl -X POST http://localhost:11435/api/generate \
    -H "Content-Type: application/json" \
    -d '{
        "model": "llama2:7b",
        "prompt": "What is the capital of France? Answer in one sentence.",
        "stream": false
    }' &

# Test streaming through wrapper
echo -e "\n\nTesting streaming inference through wrapper..."
curl -X POST http://localhost:11435/api/generate \
    -H "Content-Type: application/json" \
    -d '{
        "model": "llama2:7b",
        "prompt": "List three colors of the rainbow.",
        "stream": true
    }' &

# Wait for requests to complete
wait

# Check metrics
echo -e "\n\nChecking LLM metrics..."
echo "Tokens per second:"
curl -s http://localhost:9202/metrics | grep "llm_tokens_per_second" | grep -v "^#"

echo -e "\nActive requests:"
curl -s http://localhost:9202/metrics | grep "llm_active_requests" | grep -v "^#"

echo -e "\nTokens generated:"
curl -s http://localhost:9202/metrics | grep "llm_tokens_generated_total" | grep -v "^#"

echo -e "\nInference latency:"
curl -s http://localhost:9202/metrics | grep "llm_inference_latency_seconds_count" | grep -v "^#"

echo -e "\nWrapper metrics:"
curl -s http://localhost:9203/metrics | grep -E "llm_tokens_per_second|llm_active_requests" | grep -v "^#"

echo -e "\n\nGrafana dashboard available at: http://localhost:3000"
echo "Look for 'LLM Inference Monitoring' dashboard"
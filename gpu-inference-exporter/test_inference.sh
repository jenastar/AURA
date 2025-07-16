#!/bin/bash

echo "GPU Memory Inference Test"
echo "========================"
echo

# Check if nvidia-smi is available
if ! command -v nvidia-smi &> /dev/null; then
    echo "Error: nvidia-smi not found. Please ensure NVIDIA drivers are installed."
    exit 1
fi

# Show current GPU status
echo "1. Current GPU Status:"
nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv
echo

# Show running processes
echo "2. GPU Processes (visible to nvidia-smi):"
nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv
echo

# Check for containers with GPU access
echo "3. Containers with GPU access:"
docker ps --format "table {{.Names}}\t{{.ID}}" | while read name id; do
    if [ "$name" != "NAMES" ]; then
        runtime=$(docker inspect $id --format '{{.HostConfig.Runtime}}' 2>/dev/null)
        devices=$(docker inspect $id --format '{{json .HostConfig.DeviceRequests}}' 2>/dev/null | grep -c nvidia)
        if [ "$runtime" = "nvidia" ] || [ "$devices" -gt 0 ]; then
            echo "  - $name (ID: $id)"
        fi
    fi
done
echo

# Start the exporter
echo "4. Starting GPU Inference Exporter..."
python3 gpu_inference_exporter.py &
EXPORTER_PID=$!
sleep 5

# Check metrics
echo "5. Sample Metrics:"
echo "   Total GPU Memory:"
curl -s localhost:9201/metrics | grep "^gpu_memory_total_bytes"
echo
echo "   Known vs Unknown Memory:"
curl -s localhost:9201/metrics | grep "^gpu_memory_known_bytes"
curl -s localhost:9201/metrics | grep "^gpu_memory_unknown_bytes"
echo
echo "   Container GPU Memory (Inferred):"
curl -s localhost:9201/metrics | grep "^container_gpu_memory_bytes.*inference"
echo

# Cleanup
kill $EXPORTER_PID 2>/dev/null

echo "Test complete!"
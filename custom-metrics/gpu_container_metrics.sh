#!/bin/bash

# Generate GPU container metrics for Prometheus
# Maps nvidia-smi process data to Docker containers

METRICS_FILE="/etc/custom-metrics/gpu_container_metrics.prom"
TEMP_FILE=$(mktemp)

# Write metric headers
cat > "$TEMP_FILE" << 'EOF'
# HELP docker_container_gpu_usage_percent Container GPU utilization percentage
# TYPE docker_container_gpu_usage_percent gauge
# HELP docker_container_gpu_memory_usage_bytes Container GPU memory usage in bytes
# TYPE docker_container_gpu_memory_usage_bytes gauge
EOF

# Function to get container info from PID
get_container_from_pid() {
    local pid=$1
    local container_id=""
    
    # Check if PID exists in any container
    for container in $(docker ps -q); do
        # Get the main process PID of the container
        local container_pid=$(docker inspect -f '{{.State.Pid}}' "$container" 2>/dev/null)
        
        # Check if our GPU process PID is within this container's PID namespace
        if [ -n "$container_pid" ] && [ -d "/proc/$container_pid" ]; then
            # Check if the GPU process is a child of this container
            if grep -q "^$container_pid\$" "/proc/$pid/status" 2>/dev/null || \
               nsenter -t "$container_pid" -p pgrep -P 1 | grep -q "^$pid\$" 2>/dev/null; then
                container_id="$container"
                break
            fi
        fi
    done
    
    echo "$container_id"
}

# Get GPU process information from nvidia-smi
if command -v nvidia-smi >/dev/null 2>&1; then
    # Query compute processes with PID, GPU utilization, and memory
    nvidia-smi --query-compute-apps=pid,gpu_uuid,used_gpu_memory --format=csv,noheader,nounits 2>/dev/null | while IFS=', ' read -r pid gpu_uuid gpu_memory; do
        if [ -n "$pid" ] && [ "$pid" != "[Not Supported]" ]; then
            # Try to find which container this PID belongs to
            container_id=$(get_container_from_pid "$pid")
            
            if [ -n "$container_id" ]; then
                # Get container details
                container_info=$(docker inspect "$container_id" 2>/dev/null | jq -r '.[0] | {name: .Name, project: .Config.Labels.project}')
                container_name=$(echo "$container_info" | jq -r '.name' | sed 's/^\///')
                project_label=$(echo "$container_info" | jq -r '.project // "unknown"')
                
                # Get GPU index from UUID
                gpu_index=$(nvidia-smi -L | grep "$gpu_uuid" | cut -d':' -f1 | awk '{print $2}')
                
                # Get current GPU utilization for this specific process
                # Note: nvidia-smi doesn't provide per-process utilization, so we'll mark it as active
                echo "docker_container_gpu_memory_usage_bytes{container_id=\"${container_id:0:12}\",container_name=\"${container_name}\",project=\"${project_label}\",gpu=\"${gpu_index}\"} $((gpu_memory * 1024 * 1024))" >> "$TEMP_FILE"
            fi
        fi
    done
    
    # Also add GPU utilization based on running containers
    # This is an approximation - shows which containers have GPU processes
    docker ps --format "json" | while IFS= read -r line; do
        if [ -n "$line" ]; then
            container_id=$(echo "$line" | jq -r '.ID')
            container_name=$(echo "$line" | jq -r '.Names')
            
            # Check if container has GPU access
            gpu_devices=$(docker inspect "$container_id" 2>/dev/null | jq -r '.[0].HostConfig.DeviceRequests[]? | select(.Driver == "nvidia") | .DeviceIDs[]?' 2>/dev/null)
            
            if [ -n "$gpu_devices" ] || [ "$(docker inspect "$container_id" 2>/dev/null | jq -r '.[0].HostConfig.Runtime')" = "nvidia" ]; then
                # Get project label
                project_label=$(docker inspect "$container_id" 2>/dev/null | jq -r '.[0].Config.Labels.project // "unknown"')
                
                # Check if this container has any GPU processes
                container_pid=$(docker inspect -f '{{.State.Pid}}' "$container_id" 2>/dev/null)
                if [ -n "$container_pid" ] && nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | grep -q "$container_pid"; then
                    # Container has active GPU processes - report as active (1.0 = active, 0.0 = idle)
                    echo "docker_container_gpu_usage_percent{container_id=\"${container_id:0:12}\",container_name=\"${container_name}\",project=\"${project_label}\"} 1.0" >> "$TEMP_FILE"
                else
                    # Container has GPU access but no active processes
                    echo "docker_container_gpu_usage_percent{container_id=\"${container_id:0:12}\",container_name=\"${container_name}\",project=\"${project_label}\"} 0.0" >> "$TEMP_FILE"
                fi
            fi
        fi
    done
fi

# Atomic move to final location
mv "$TEMP_FILE" "$METRICS_FILE"
#!/bin/bash

# Generate Docker container stats metrics with project labels for Prometheus
# This replaces cAdvisor functionality for individual container metrics

METRICS_FILE="/etc/custom-metrics/docker_stats.prom"
TEMP_FILE=$(mktemp)

cat > "$TEMP_FILE" << 'EOF'
# HELP docker_container_cpu_usage_percent Container CPU usage percentage
# TYPE docker_container_cpu_usage_percent gauge
# HELP docker_container_memory_usage_bytes Container memory usage in bytes
# TYPE docker_container_memory_usage_bytes gauge
# HELP docker_container_memory_limit_bytes Container memory limit in bytes
# TYPE docker_container_memory_limit_bytes gauge
# HELP docker_container_network_rx_bytes Container network received bytes
# TYPE docker_container_network_rx_bytes counter
# HELP docker_container_network_tx_bytes Container network transmitted bytes
# TYPE docker_container_network_tx_bytes counter
# HELP docker_container_status Container status (1=running, 0=stopped)
# TYPE docker_container_status gauge
# HELP docker_container_restart_count Container restart count
# TYPE docker_container_restart_count counter
# HELP docker_container_block_io_read_bytes Container block I/O read bytes
# TYPE docker_container_block_io_read_bytes counter
# HELP docker_container_block_io_write_bytes Container block I/O write bytes
# TYPE docker_container_block_io_write_bytes counter
EOF

# Get all containers (running and stopped) and their stats
docker ps -a --format "json" | while IFS= read -r line; do
    if [ -n "$line" ]; then
        # Extract container info
        container_id=$(echo "$line" | grep -o '"ID":"[^"]*"' | cut -d'"' -f4)
        container_name=$(echo "$line" | grep -o '"Names":"[^"]*"' | cut -d'"' -f4)
        container_status=$(echo "$line" | grep -o '"State":"[^"]*"' | cut -d'"' -f4)
        
        # Get project label from container inspect
        project_label=$(docker inspect "$container_id" 2>/dev/null | grep -o '"project"[[:space:]]*:[[:space:]]*"[^"]*"' | cut -d'"' -f4)
        
        if [ -n "$container_id" ] && [ -n "$project_label" ]; then
            # Container status metric (1=running, 0=stopped/other)
            if [ "$container_status" = "running" ]; then
                status_value=1
            else
                status_value=0
            fi
            echo "docker_container_status{container_id=\"${container_id}\",container_name=\"${container_name}\",project=\"${project_label}\",status=\"${container_status}\"} ${status_value}" >> "$TEMP_FILE"
            
            # Get restart count
            restart_count=$(docker inspect "$container_id" 2>/dev/null | grep -o '"RestartCount"[[:space:]]*:[[:space:]]*[0-9]*' | grep -o '[0-9]*$')
            if [ -n "$restart_count" ]; then
                echo "docker_container_restart_count{container_id=\"${container_id}\",container_name=\"${container_name}\",project=\"${project_label}\"} ${restart_count}" >> "$TEMP_FILE"
            fi
            
            # Only get live stats for running containers
            if [ "$container_status" = "running" ]; then
                # Get container stats
                stats=$(docker stats --no-stream --format "json" "$container_id" 2>/dev/null)
                
                if [ -n "$stats" ]; then
                    # Extract CPU percentage (remove % symbol)
                    cpu_percent=$(echo "$stats" | grep -o '"CPUPerc":"[^"]*"' | cut -d'"' -f4 | tr -d '%')
                    
                    # Extract memory usage (keep original format with units)
                    mem_usage_raw=$(echo "$stats" | grep -o '"MemUsage":"[^"]*"' | cut -d'"' -f4 | cut -d'/' -f1 | xargs)
                    mem_limit_raw=$(echo "$stats" | grep -o '"MemUsage":"[^"]*"' | cut -d'"' -f4 | cut -d'/' -f2 | xargs)
                    
                    # Extract network I/O (keep original format with units)
                    net_input_raw=$(echo "$stats" | grep -o '"NetIO":"[^"]*"' | cut -d'"' -f4 | cut -d'/' -f1 | xargs)
                    net_output_raw=$(echo "$stats" | grep -o '"NetIO":"[^"]*"' | cut -d'"' -f4 | cut -d'/' -f2 | xargs)
                    
                    # Extract block I/O (keep original format with units)
                    block_input_raw=$(echo "$stats" | grep -o '"BlockIO":"[^"]*"' | cut -d'"' -f4 | cut -d'/' -f1 | xargs)
                    block_output_raw=$(echo "$stats" | grep -o '"BlockIO":"[^"]*"' | cut -d'"' -f4 | cut -d'/' -f2 | xargs)
                    
                    # Function to convert human readable to bytes
                    convert_to_bytes() {
                        local value="$1"
                        # Extract number and unit using sed
                        local num=$(echo "$value" | sed 's/[^0-9.]//g')
                        local unit=$(echo "$value" | sed 's/[0-9.]//g' | tr '[:upper:]' '[:lower:]')
                        
                        # Default to 0 if no number found
                        if [ -z "$num" ]; then
                            echo "0"
                            return
                        fi
                        
                        # Convert based on unit
                        case "$unit" in
                            b|"")
                                echo "${num%.*}"
                                ;;
                            kb|k)
                                echo "$(echo "$num * 1024" | bc | cut -d. -f1)"
                                ;;
                            mb|m|mib)
                                echo "$(echo "$num * 1024 * 1024" | bc | cut -d. -f1)"
                                ;;
                            gb|g|gib)
                                echo "$(echo "$num * 1024 * 1024 * 1024" | bc | cut -d. -f1)"
                                ;;
                            tb|t|tib)
                                echo "$(echo "$num * 1024 * 1024 * 1024 * 1024" | bc | cut -d. -f1)"
                                ;;
                            *)
                                echo "${num%.*}"
                                ;;
                        esac
                    }
                
                    mem_usage_bytes=$(convert_to_bytes "$mem_usage_raw")
                    mem_limit_bytes=$(convert_to_bytes "$mem_limit_raw")
                    net_input_bytes=$(convert_to_bytes "$net_input_raw")
                    net_output_bytes=$(convert_to_bytes "$net_output_raw")
                    block_input_bytes=$(convert_to_bytes "$block_input_raw")
                    block_output_bytes=$(convert_to_bytes "$block_output_raw")
                    
                    # Output metrics for running containers
                    if [ -n "$cpu_percent" ] && [ "$cpu_percent" != "" ]; then
                        echo "docker_container_cpu_usage_percent{container_id=\"${container_id}\",container_name=\"${container_name}\",project=\"${project_label}\"} ${cpu_percent}" >> "$TEMP_FILE"
                    fi
                    
                    if [ -n "$mem_usage_bytes" ] && [ "$mem_usage_bytes" != "0" ]; then
                        echo "docker_container_memory_usage_bytes{container_id=\"${container_id}\",container_name=\"${container_name}\",project=\"${project_label}\"} ${mem_usage_bytes}" >> "$TEMP_FILE"
                    fi
                    
                    if [ -n "$mem_limit_bytes" ] && [ "$mem_limit_bytes" != "0" ]; then
                        echo "docker_container_memory_limit_bytes{container_id=\"${container_id}\",container_name=\"${container_name}\",project=\"${project_label}\"} ${mem_limit_bytes}" >> "$TEMP_FILE"
                    fi
                    
                    if [ -n "$net_input_bytes" ] && [ "$net_input_bytes" != "0" ]; then
                        echo "docker_container_network_rx_bytes{container_id=\"${container_id}\",container_name=\"${container_name}\",project=\"${project_label}\"} ${net_input_bytes}" >> "$TEMP_FILE"
                    fi
                    
                    if [ -n "$net_output_bytes" ] && [ "$net_output_bytes" != "0" ]; then
                        echo "docker_container_network_tx_bytes{container_id=\"${container_id}\",container_name=\"${container_name}\",project=\"${project_label}\"} ${net_output_bytes}" >> "$TEMP_FILE"
                    fi
                    
                    if [ -n "$block_input_bytes" ] && [ "$block_input_bytes" != "0" ]; then
                        echo "docker_container_block_io_read_bytes{container_id=\"${container_id}\",container_name=\"${container_name}\",project=\"${project_label}\"} ${block_input_bytes}" >> "$TEMP_FILE"
                    fi
                    
                    if [ -n "$block_output_bytes" ] && [ "$block_output_bytes" != "0" ]; then
                        echo "docker_container_block_io_write_bytes{container_id=\"${container_id}\",container_name=\"${container_name}\",project=\"${project_label}\"} ${block_output_bytes}" >> "$TEMP_FILE"
                    fi
                fi
            fi
        fi
    fi
done

# Atomic move to final location
mv "$TEMP_FILE" "$METRICS_FILE"
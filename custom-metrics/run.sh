#!/bin/bash

# Run custom metrics collection scripts in a loop
while true; do
    echo "Running custom metrics collection..."
    
    # Run container labels mapping
    if [ -x /scripts/container_labels_mapping.sh ]; then
        /scripts/container_labels_mapping.sh
    fi
    
    # Run docker stats metrics
    if [ -x /scripts/docker_stats_metrics.sh ]; then
        /scripts/docker_stats_metrics.sh
    fi
    
    # Run GPU container metrics
    if [ -x /scripts/gpu_container_metrics.sh ]; then
        /scripts/gpu_container_metrics.sh
    fi
    
    # Fix permissions so node exporter can read the files
    chmod 644 /etc/custom-metrics/*.prom 2>/dev/null || true
    
    # Sleep for 5 seconds before next collection
    sleep 5
done
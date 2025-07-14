#!/bin/bash

# Generate container label mapping metrics for Prometheus
# This creates a bridge between cAdvisor container IDs and Docker container labels

METRICS_FILE="/mnt/c/Users/jenas/dev/benchMarking/custom-metrics/container_labels.prom"

# Create temp file for atomic write
TEMP_FILE=$(mktemp)

cat > "$TEMP_FILE" << 'EOF'
# HELP container_label_info Container label information mapping
# TYPE container_label_info gauge
EOF

# Get Docker container information with labels
docker ps --format "json" | while IFS= read -r line; do
    if [ -n "$line" ]; then
        # Extract container ID and name
        container_id=$(echo "$line" | grep -o '"ID":"[^"]*"' | cut -d'"' -f4)
        container_name=$(echo "$line" | grep -o '"Names":"[^"]*"' | cut -d'"' -f4)
        
        # Extract project label - get the last occurrence which should be our custom project label
        project_label=$(echo "$line" | grep -o 'project=[^,}]*' | tail -1 | cut -d'=' -f2 | tr -d '"')
        
        if [ -n "$container_id" ] && [ -n "$project_label" ]; then
            # Create metric with container ID and project label
            echo "container_label_info{container_id=\"${container_id}\",container_name=\"${container_name}\",project=\"${project_label}\"} 1" >> "$TEMP_FILE"
        fi
    fi
done

# Atomic move to final location
mv "$TEMP_FILE" "$METRICS_FILE"
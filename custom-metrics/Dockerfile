FROM nvidia/cuda:11.8.0-base-ubuntu22.04

# Install required packages
RUN apt-get update && apt-get install -y \
    bash \
    docker.io \
    bc \
    jq \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create directories
RUN mkdir -p /scripts /etc/custom-metrics

# Copy scripts
COPY container_labels_mapping.sh /scripts/
COPY docker_stats_metrics.sh /scripts/
COPY gpu_container_metrics.sh /scripts/
COPY run.sh /scripts/

# Make scripts executable
RUN chmod +x /scripts/*.sh

# Run the collection script
CMD ["/scripts/run.sh"]
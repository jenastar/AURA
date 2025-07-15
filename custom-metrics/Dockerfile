FROM alpine:latest

# Install bash, docker client, and bc for calculations
RUN apk add --no-cache bash docker-cli bc

# Create directories
RUN mkdir -p /scripts /etc/custom-metrics

# Copy scripts
COPY container_labels_mapping.sh /scripts/
COPY docker_stats_metrics.sh /scripts/
COPY run.sh /scripts/

# Make scripts executable
RUN chmod +x /scripts/*.sh

# Run the collection script
CMD ["/scripts/run.sh"]
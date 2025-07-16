FROM nvidia/cuda:11.8.0-base-ubuntu22.04

# Install Python and required system packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --no-cache-dir \
    prometheus-client==0.19.0 \
    nvidia-ml-py==12.535.133

# Create app directory
WORKDIR /app

# Copy the exporter script
COPY gpu_inference_exporter.py /app/

# Make it executable
RUN chmod +x /app/gpu_inference_exporter.py

# Expose metrics port
EXPOSE 9201

# Run the exporter
CMD ["python3", "/app/gpu_inference_exporter.py"]
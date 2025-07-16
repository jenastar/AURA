FROM python:3.10-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    prometheus-client==0.19.0 \
    requests==2.31.0 \
    aiohttp==3.9.1 \
    psutil==5.9.6

# Copy application files
COPY llm_metrics_exporter.py /app/
COPY ollama_inference_wrapper.py /app/

# Make scripts executable
RUN chmod +x /app/*.py

# Default to running the metrics exporter
CMD ["python", "/app/llm_metrics_exporter.py"]
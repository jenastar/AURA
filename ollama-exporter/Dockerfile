FROM python:3.11-slim

# Install required packages
RUN pip install --no-cache-dir \
    prometheus-client==0.19.0 \
    requests==2.31.0

# Create app directory
WORKDIR /app

# Copy the exporter script
COPY ollama_exporter.py /app/

# Make it executable
RUN chmod +x /app/ollama_exporter.py

# Expose metrics port
EXPOSE 9200

# Run the exporter
CMD ["python", "/app/ollama_exporter.py"]
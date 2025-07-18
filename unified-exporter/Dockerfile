FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the exporter script
COPY unified_exporter.py .

# Make the script executable
RUN chmod +x unified_exporter.py

# Default environment variables
ENV EXPORTER_PORT=9999
ENV COLLECTION_INTERVAL=10
ENV OLLAMA_HOST=host.docker.internal
ENV OLLAMA_PORT=11434

EXPOSE 9999

CMD ["python", "unified_exporter.py"]
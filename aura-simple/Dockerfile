FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the exporter scripts
COPY simple_unified_exporter.py .

# Make the script executable
RUN chmod +x simple_unified_exporter.py

# Default environment variables
ENV EXPORTER_PORT=9999
ENV COLLECTION_INTERVAL=15

EXPOSE 9999

CMD ["python", "simple_unified_exporter.py"]
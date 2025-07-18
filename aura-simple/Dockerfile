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

# Copy the mega exporter script
COPY mega_exporter.py .

# Make the script executable
RUN chmod +x mega_exporter.py

# Default environment variables
ENV EXPORTER_PORT=8080
ENV COLLECTION_INTERVAL=15
ENV PROMETHEUS_EMBEDDED=true
ENV BASIC_AUTH_USER=admin
ENV BASIC_AUTH_PASSWORD=admin

EXPOSE 8080

CMD ["python", "mega_exporter.py"]
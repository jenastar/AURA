FROM python:3.10-slim

WORKDIR /app

# Install core dependencies only
RUN pip install --no-cache-dir \
    prometheus-client==0.19.0 \
    requests==2.31.0 \
    numpy==1.24.3 \
    psutil==5.9.6 \
    chromadb==0.4.15

# Copy application files
COPY vector_db_metrics_exporter.py /app/
COPY chromadb_wrapper.py /app/
COPY pinecone_wrapper.py /app/
COPY faiss_wrapper.py /app/
COPY chromadb_metrics_collector.py /app/

# Copy example files
COPY example*.py /app/

# Make scripts executable
RUN chmod +x /app/*.py

# Create data directory for FAISS persistence
RUN mkdir -p /app/data

# Default to running the metrics exporter
CMD ["python", "/app/vector_db_metrics_exporter.py"]
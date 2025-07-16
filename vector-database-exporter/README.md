# Vector Database Monitoring - Test Setup

This directory contains a complete test setup for vector database monitoring with a real RAG (Retrieval Augmented Generation) application.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│                 │     │                  │     │                 │
│  Test RAG App   │────▶│    ChromaDB      │◀────│  Vector DB      │
│  (Q&A System)   │     │  (Vector Store)  │     │   Exporter      │
│                 │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                                                   ┌─────────────────┐
                                                   │   Prometheus    │
                                                   │   (Metrics)     │
                                                   └─────────────────┘
```

## Quick Start

### 1. Start the Test Environment

```bash
cd /mnt/c/dev/aura/vector-database-exporter
docker compose -f docker-compose.test.yml up -d
```

This starts:
- **ChromaDB**: Real vector database instance
- **Vector DB Exporter**: Configured to monitor ChromaDB
- **Test RAG App**: Simulates a documentation Q&A system

### 2. View the Metrics

The test setup exposes metrics on port 9206:
```bash
# Check raw metrics
curl http://localhost:9206/metrics | grep vector_db

# See specific metrics
curl http://localhost:9206/metrics | grep -E "vector_db_(embeddings|insertions|similarity)"
```

### 3. Monitor in Grafana

The metrics are automatically scraped by Prometheus and displayed in the Vector Database Monitoring dashboard:
- Navigate to http://localhost:3000
- Login with admin/admin
- Go to "Vector Database Monitoring" dashboard

## What the Test Application Does

The test RAG application simulates a real-world documentation Q&A system:

1. **Document Indexing**: Indexes 12 sample documents about monitoring, AI, and containers
2. **User Queries**: Simulates users asking questions like:
   - "How do I monitor containers with Prometheus?"
   - "What is RAG and how does it work?"
   - "How can I visualize metrics in Grafana?"

3. **Continuous Operations**:
   - Performs 5-10 searches every iteration
   - Occasionally adds new documents
   - Sometimes rebuilds the entire index
   - Tracks all operations with metrics

## Metrics Generated

The test application generates real metrics for:

- **Embeddings**: 
  - `vector_db_embeddings_generated_total` - Document embeddings created
  - `vector_db_embedding_generation_seconds` - Time to generate embeddings

- **Insertions**:
  - `vector_db_insertions_total` - Vectors inserted into ChromaDB
  - `vector_db_insertion_seconds` - Time to insert vectors

- **Searches**:
  - `vector_db_similarity_searches_total` - Number of searches performed
  - `vector_db_similarity_search_seconds` - Search latency
  - `vector_db_similarity_scores` - Distribution of similarity scores

- **Collection Stats**:
  - `vector_db_collection_size` - Number of documents in collection
  - `vector_db_collection_dimension` - Embedding dimension (384 for MiniLM)

## Using in Production

To adapt this for your own vector database:

### 1. For ChromaDB

```python
from chromadb_wrapper import ChromaDBWrapper
import chromadb

# Initialize client
client = chromadb.HttpClient(host="your-chromadb-host")

# Create wrapper for automatic metrics
wrapper = ChromaDBWrapper(client)

# Use wrapper methods - metrics are tracked automatically
wrapper.add_documents("my_collection", documents)
results = wrapper.search_documents("my_collection", "query")
```

### 2. For Pinecone

```python
from pinecone_wrapper import PineconeWrapper
import pinecone

# Initialize Pinecone
pinecone.init(api_key="your-key")
index = pinecone.Index("your-index")

# Create wrapper
wrapper = PineconeWrapper(index)

# Use wrapper methods
wrapper.upsert_documents(documents)
results = wrapper.search_documents("query")
```

### 3. For FAISS

```python
from faiss_wrapper import FAISSWrapper

# Create wrapper
wrapper = FAISSWrapper(dimension=768, index_type="hnsw")

# Create collection and use
wrapper.create_collection("my_vectors")
wrapper.add_documents("my_vectors", documents)
results = wrapper.search_documents("my_vectors", "query")
```

## Configuration

### Environment Variables

- `CHROMADB_HOST`: ChromaDB host (default: localhost)
- `CHROMADB_PORT`: ChromaDB port (default: 8000)
- `EXPORTER_PORT`: Metrics exporter port (default: 9205)
- `SCRAPE_INTERVAL`: How often to collect metrics (default: 10s)
- `DEMO_MODE`: Set to 'false' for real monitoring (default: true)

### Docker Compose Override

For production use, create a `docker-compose.override.yml`:

```yaml
services:
  vector_db_exporter:
    environment:
      - DEMO_MODE=false
      - CHROMADB_HOST=your-chromadb-host
      - CHROMADB_PORT=8000
```

## Troubleshooting

### No metrics showing up?
1. Check ChromaDB is running: `curl http://localhost:8000/api/v1/heartbeat`
2. Check exporter logs: `docker logs test_vector_db_exporter`
3. Verify metrics endpoint: `curl http://localhost:9206/metrics`

### Connection errors?
- Ensure ChromaDB is accessible from the exporter container
- Check network connectivity between containers
- Verify ChromaDB is configured to accept external connections

### High latency metrics?
- This is normal for the first embedding generation (model loading)
- Subsequent operations should be faster
- Consider using a GPU for faster embedding generation

## Extending the Test

To add your own test scenarios:

1. Modify `SAMPLE_DOCS` in `test_rag_application.py` to add your documents
2. Add new queries to `SAMPLE_QUERIES`
3. Implement additional operations in the `TestRAGApplication` class

## Stop the Test

```bash
docker compose -f docker-compose.test.yml down -v
```

This stops all containers and removes the test data.
# Vector Database Test Stack

This is a separate Docker Compose stack for testing vector database operations independently from the main AURA monitoring stack.

## Purpose

This stack provides:
- A dedicated ChromaDB instance for testing
- Test applications that generate continuous vector operations
- Complete isolation from the main monitoring infrastructure

## Quick Start

### Start the test stack
```bash
docker compose up -d
```

### Stop the test stack
```bash
docker compose down
```

### View logs
```bash
docker compose logs -f
```

## Services

### ChromaDB (test_chromadb)
- **Port**: 8001 (mapped from internal 8000)
- **Purpose**: Vector database for testing
- **Data**: Persisted in `chromadb_test_data` volume

### Vector Test App (vector_test_app)
- **Purpose**: Generates continuous vector operations
- **Features**: Simple embedding generation and searches

### RAG Test App (rag_test_app) - Optional
- **Purpose**: More complex RAG application testing
- **Start with**: `docker compose --profile rag up -d`

## Connecting to Main Monitoring Stack

The main monitoring stack can collect metrics from this test stack by:

1. Ensuring both stacks share a network:
   ```bash
   docker network connect aura_mon_network test_chromadb
   ```

2. Configuring the vector DB exporter in the main stack to point to:
   - Host: `test_chromadb` (if connected to same network)
   - Port: `8000` (internal port)
   - Or use `host.docker.internal:8001` from main stack

## Management Commands

### Start only ChromaDB
```bash
docker compose up -d chromadb
```

### Restart test application
```bash
docker compose restart vector_test_app
```

### Clean up everything (including volumes)
```bash
docker compose down -v
```

### View ChromaDB collections
```bash
curl http://localhost:8001/api/v1/collections
```

### Check if ChromaDB is healthy
```bash
curl http://localhost:8001/api/v1/heartbeat
```

## Environment Variables

You can customize the behavior by creating a `.env` file:

```env
# ChromaDB settings
CHROMADB_PORT=8001

# Test app settings
TEST_BATCH_SIZE=10
TEST_INTERVAL=30
```

## Troubleshooting

### Port conflicts
If port 8001 is already in use, change it in docker-compose.yml:
```yaml
ports:
  - "8002:8000"  # Use 8002 instead
```

### Container can't connect
Ensure the containers are on the same network:
```bash
docker network ls
docker network inspect vector_test_network
```

### View test app output
```bash
docker logs vector_test_app -f
```
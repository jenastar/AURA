# Vector Database Monitoring - Project Labels Summary

## Overview
All components of the vector database monitoring feature have been properly labeled with project tags to ensure consistent organization and filtering.

## Project Label Structure

### 1. **Main Monitoring Stack** (`project=mon`)
Located in `/mnt/c/dev/aura/docker-compose.yml`:
- `vector_db_exporter` service - labeled with `project=mon`
- Integrates with the main monitoring network
- Accessible at port 9205

### 2. **Test Environment** (`project=vector-db-test`)
Located in `/mnt/c/dev/aura/vector-database-exporter/docker-compose.test.yml`:
- All services labeled with `project=vector-db-test`:
  - `chromadb` - Test ChromaDB instance
  - `vector_db_exporter_real` - Exporter configured for real ChromaDB
  - `vector_test_app` - Test application generating real metrics
- Separate test network labeled accordingly
- Test volumes labeled for easy cleanup

### 3. **Standalone ChromaDB** (`project=vector-db`)
Located in `/mnt/c/dev/aura/vector-database-exporter/chromadb-compose.yml`:
- ChromaDB service for real-world examples
- Uses external `mon_network` for integration
- Additional labels:
  - `component=database`
  - `db_type=chromadb`

## Label Benefits

1. **Easy Filtering**: Can filter all vector DB components with:
   ```bash
   docker ps --filter "label=project=vector-db-test"
   ```

2. **Organized Cleanup**: Remove test environment completely:
   ```bash
   docker compose -f docker-compose.test.yml down -v
   ```

3. **Monitoring Integration**: Main stack components show up in container group dashboards

4. **Resource Tracking**: Can track resource usage by project label

## Verification Commands

Check all labeled containers:
```bash
# Main monitoring stack
docker ps --filter "label=project=mon" --format "table {{.Names}}\t{{.Labels}}"

# Test environment
docker ps --filter "label=project=vector-db-test" --format "table {{.Names}}\t{{.Labels}}"

# Standalone ChromaDB
docker ps --filter "label=project=vector-db" --format "table {{.Names}}\t{{.Labels}}"
```

## Dashboard Integration

The Container Groups dashboard (ID: 2) automatically groups containers by project label:
- Containers with `project=mon` appear under "Monitoring Infrastructure"
- Test containers with `project=vector-db-test` appear separately
- Enables project-based resource tracking and alerting

## Best Practices

1. Always include project labels in docker-compose files
2. Use consistent naming: `project=<feature>-test` for test environments
3. Add component labels for finer-grained filtering
4. Label volumes and networks for complete lifecycle management
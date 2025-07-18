# AURA - Agentic Unified Resource Analytics

A streamlined Docker-based monitoring stack for comprehensive system, container, and GPU monitoring.

## Architecture

### Core Services

1. **Unified Exporter** (port 9999)
   - Consolidates all custom metrics in one service
   - Provides: Docker container metrics, GPU metrics, vector database metrics
   - Implements GPU memory inference for invisible workloads

2. **Prometheus** (port 9090)
   - Time-series database for metrics storage
   - Configured to scrape all exporters

3. **Grafana** (port 3000)
   - Visualization platform with pre-configured dashboards
   - Default credentials: admin/admin

### Supporting Exporters

4. **Node Exporter** (port 9100) - System-level metrics
5. **cAdvisor** (port 8080) - Container resource usage
6. **DCGM Exporter** (port 9400) - NVIDIA GPU metrics
7. **Process Exporter** (port 9256) - Process group metrics
8. **Blackbox Exporter** (port 9115) - Endpoint monitoring

## Quick Start

```bash
# Start all services
docker compose up -d

# Check service status
docker compose ps

# Access dashboards
# Grafana: http://localhost:3000
# Prometheus: http://localhost:9090
```

## Dashboards

1. **System Infrastructure Overview** - High-level system view
2. **Container Groups by Project** - Containers grouped by project label
3. **GPU & Process Performance** - GPU utilization and process metrics
4. **Container-Level Monitoring** - Detailed container metrics
5. **System-Level Monitoring** - Host system metrics
6. **Vector Database Monitoring** - Vector DB health and performance

## Container Labeling

Add these labels to your containers for proper grouping:
```yaml
labels:
  - "project=your-project-name"
  - "component=service-type"
  - "service=specific-service"
```

## Metrics Overview

- `docker_container_*` - Container resource metrics
- `gpu_memory_*` - GPU memory usage
- `container_gpu_memory_bytes` - GPU usage by container
- `vector_db_*` - Vector database metrics
- `namedprocess_*` - Process group metrics
- `node_*` - System metrics
- `container_*` - cAdvisor metrics
- `dcgm_*` - NVIDIA GPU metrics
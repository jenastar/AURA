# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

AURA (Agentic Unified Resource Analytics) is a Docker-based monitoring infrastructure that provides comprehensive system, container, GPU, and process monitoring through Prometheus and Grafana.

## Architecture

### Service Components
- **Prometheus** (9090): Central metrics database, scrapes all exporters every 15 seconds
- **Grafana** (3000): Visualization layer with pre-configured dashboards
- **Node Exporter** (9100): System-level metrics (CPU, memory, disk, network)
- **cAdvisor** (8080): Container resource usage and performance metrics
- **DCGM Exporter** (9400): NVIDIA GPU metrics (requires NVIDIA runtime)
- **Blackbox Exporter** (9115): HTTP/TCP endpoint monitoring
- **Process Exporter** (9256): Process-level monitoring
- **Custom Metrics** (9101): Additional metrics via shell scripts
- **Docker Socket Proxy** (2376): Secure Docker API access

### Network Configuration
- All services communicate via `mon_network` Docker bridge
- Services labeled with `project=mon` for self-monitoring
- Test containers use `benchmarking_mon_network`

## Key Commands

### Service Management
```bash
# Start all services
docker compose up -d

# View service status
docker compose ps

# View logs (all services or specific)
docker compose logs -f [service_name]

# Stop all services
docker compose down

# Restart specific service
docker compose restart [service_name]

# Deploy test containers for monitoring validation
docker compose -f test-containers.yml up -d
```

### Debugging & Validation
```bash
# Check Prometheus targets status
curl http://localhost:9090/api/v1/targets

# Test blackbox probe
curl "http://localhost:9115/probe?target=http://localhost:3000&module=http_2xx"

# Verify custom metrics endpoint
curl http://localhost:9101/metrics

# Check container labels mapping
docker exec -it custom-metrics cat /metrics/container_labels.prom
```

## Configuration Files

### Critical Configurations
- `prometheus/prometheus.yml`: Scrape jobs and targets configuration
- `docker-compose.yml`: Service definitions and container configuration
- `grafana/provisioning/`: Dashboard and datasource provisioning
- `blackbox/config.yml`: HTTP/TCP probe modules configuration
- `process-exporter/config.yml`: Process monitoring patterns
- `custom-metrics/*.sh`: Shell scripts generating custom metrics

### Dashboard Structure
- `grafana/provisioning/dashboards/`:
  - `1-system-infrastructure.json`: System and service health
  - `2-container-groups.json`: Container metrics by project label
  - `3-gpu-process-performance.json`: GPU and process monitoring
  - `Container Monitoring/`: Additional container-specific dashboards

## Development Workflow

### Adding New Exporters
1. Add service definition to `docker-compose.yml`
2. Configure scrape job in `prometheus/prometheus.yml`
3. Create dashboard in `grafana/provisioning/dashboards/`
4. Restart stack: `docker compose down && docker compose up -d`

### Creating Custom Metrics
1. Add shell script to `custom-metrics/` directory
2. Script must output Prometheus format to stdout
3. Container automatically executes all `.sh` files
4. Metrics available at `http://localhost:9101/metrics`

### Container Monitoring
- Label containers with `project=<name>` for automatic grouping
- Labels enable project-based dashboard filtering
- Custom metrics scripts map container IDs to project labels

### Modifying Dashboards
1. Edit dashboard in Grafana UI
2. Export JSON via Dashboard Settings → JSON Model
3. Save to `grafana/provisioning/dashboards/`
4. Restart Grafana: `docker compose restart grafana`

## Data Persistence
- Prometheus data: `prometheus_data` volume (200-hour retention)
- Grafana data: `grafana_data` volume
- Volumes persist through container restarts

## Credentials & Access
- Grafana: `admin/admin` (initial login)
- All services accessible via localhost ports
- No authentication on metrics endpoints (secure your network)

## GPU Monitoring Requirements
- NVIDIA drivers installed on host
- NVIDIA Container Toolkit installed
- Verify with: `docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi`
- DCGM exporter requires `runtime: nvidia` in docker-compose

## Alert Configuration
- Alert rules can be added to `prometheus/alert.rules` (currently not implemented)
- Uncomment `rule_files` section in `prometheus/prometheus.yml` to enable
- Configure alertmanager for notification routing

## Performance Considerations
- Prometheus scrapes every 15 seconds (configurable in `prometheus.yml`)
- Custom metrics scripts run continuously with 10-second intervals
- cAdvisor can be resource-intensive with many containers
- Adjust retention period based on disk space availability
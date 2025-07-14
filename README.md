# Monitoring Stack

Complete Docker-based monitoring infrastructure with Prometheus, Grafana, GPU monitoring, and container metrics.

[![jenastar/monitoring context](https://badge.forgithub.com/jenastar/monitoring)](https://uithub.com/jenastar/monitoring)


### Prerequisites
- Docker Desktop (Windows/Mac) or Docker Engine + Docker Compose (Linux)
- For GPU monitoring: NVIDIA drivers and NVIDIA Container Toolkit
- Git

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/jenastar/monitoring.git
   cd monitoring
   ```

2. **Start the monitoring stack**
   ```bash
   docker compose up -d
   ```

3. **Verify all services are running**
   ```bash
   docker compose ps
   ```

4. **Access the dashboards**
   - Grafana: http://localhost:3000 (admin/admin)
   - Prometheus: http://localhost:9090
   - cAdvisor: http://localhost:8080

### Service Ports
- **Prometheus**: 9090 - Metrics database
- **Grafana**: 3000 - Dashboard interface  
- **DCGM Exporter**: 9400 - NVIDIA GPU metrics
- **Node Exporter**: 9100 - System metrics
- **cAdvisor**: 8080 - Container metrics
- **Blackbox Exporter**: 9115 - Network/service health checks
- **Process Exporter**: 9256 - Process-level monitoring
- **Custom Metrics**: 9101 - Additional system metrics
- **Docker Socket Proxy**: 2376 - Docker API proxy

### Dashboards
The stack includes 3 pre-configured dashboards:
1. **System & Infrastructure** - CPU, memory, disk, network, service health
2. **Container Groups** - Resource usage by project labels
3. **GPU & Process Performance** - NVIDIA metrics and process monitoring

### Container Groups
Label your containers with `project=<groupname>` to automatically include them in monitoring and group dashboards.

### Troubleshooting

**Services not starting:**
```bash
# Check logs
docker compose logs -f

# Restart specific service
docker compose restart <service-name>
```

**GPU monitoring not working:**
- Ensure NVIDIA drivers are installed
- Install NVIDIA Container Toolkit
- Verify with: `docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi`

**Grafana dashboards not loading:**
- Wait 30 seconds after startup for provisioning
- Check Grafana logs: `docker compose logs grafana`

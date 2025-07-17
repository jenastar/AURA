# AURA – Agentic Unified Resource Analytics

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
The stack includes 5 pre-configured dashboards:
1. **System & Infrastructure** - CPU, memory, disk, network, service health
2. **Container Groups** - Resource usage organized by project labels
3. **GPU & Process Performance** - NVIDIA GPU metrics and process monitoring
4. **Container Level Monitoring** - Detailed per-container resource metrics
5. **System Level Monitoring** - Host system performance and health

### Container Groups
Label your containers with `project=<groupname>` to automatically include them in monitoring and group dashboards.

## Integrating External Stacks

To add monitoring for external Docker stacks, you need to create custom exporters in AURA and configure the target stack properly.

### Target Stack Requirements

**1. Docker Labels** - Add to services you want to monitor:
```yaml
labels:
  - "project=your-project-name"
  - "component=service-type"     # database, api, worker, etc.
  - "service=specific-service"   # chromadb, redis, postgres, etc.
```

**2. Network Configuration** - Use default bridge network (remove explicit networks) OR join `aura_mon_network`

### AURA Monitoring Components

**1. Custom Exporter** - Create `/exporters/your-stack-exporter/`:
```dockerfile
# Dockerfile
FROM python:3.10-slim
RUN pip install prometheus-client requests
WORKDIR /app
COPY exporter.py .
CMD ["python", "exporter.py"]
```

```python
# exporter.py - Basic template
from prometheus_client import start_http_server, Gauge
import requests
import time
import os

port = int(os.environ.get('EXPORTER_PORT', '9XXX'))
target_host = os.environ.get('TARGET_HOST', 'host.docker.internal')

# Define your metrics
service_up = Gauge('service_up', 'Service status', ['service'])

def check_service():
    try:
        response = requests.get(f"http://{target_host}:PORT/health", timeout=5)
        service_up.labels(service='your-service').set(1 if response.status_code == 200 else 0)
    except:
        service_up.labels(service='your-service').set(0)

start_http_server(port)
while True:
    check_service()
    time.sleep(15)
```

**2. Docker Compose** - Add to AURA's `docker-compose.yml`:
```yaml
your_stack_exporter:
  build: ./exporters/your-stack-exporter
  container_name: mon_your_stack_exporter
  environment:
    - EXPORTER_PORT=9XXX
    - TARGET_HOST=host.docker.internal
    - PROJECT_LABEL=mon
  ports: ["9XXX:9XXX"]
  networks: [mon_network]
  labels: ["project=mon"]
  restart: unless-stopped
```

**3. Prometheus Configuration** - Add to `prometheus/prometheus.yml`:
```yaml
- job_name: 'your-stack-name'
  static_configs:
    - targets: ['your_stack_exporter:9XXX']
      labels:
        component: 'your-component'
        project: 'mon'
```

**4. Grafana Dashboard** (Optional) - Add JSON file to `grafana/provisioning/dashboards/`

### Example Integration
The vector-db-stack integration demonstrates this pattern:
- Vector databases use default network and proper labels
- `vector_db_exporter` checks ChromaDB, Qdrant, and Weaviate health
- Metrics available immediately at startup
- Dashboard shows comprehensive vector database monitoring

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

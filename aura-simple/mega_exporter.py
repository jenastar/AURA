#!/usr/bin/env python3
"""
AURA Mega Exporter - Single container with built-in web UI and metrics
"""

import os
import time
import json
import subprocess
import threading
import logging
import requests
import psutil
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, Response
from prometheus_client import start_http_server, Gauge, Counter, Histogram, generate_latest
from prometheus_client.core import CollectorRegistry
import pynvml
import docker
from enhanced_dashboard import create_enhanced_dashboard_routes, HistoricalData, update_historical_data

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('aura-mega')

# Initialize Docker client
try:
    docker_client = docker.from_env()
    logger.info("Docker client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Docker client: {e}")
    docker_client = None

# Initialize NVIDIA ML
try:
    pynvml.nvmlInit()
    gpu_available = True
    logger.info("NVIDIA ML initialized successfully")
except Exception as e:
    logger.warning(f"NVIDIA ML not available: {e}")
    gpu_available = False

# Create Flask app
app = Flask(__name__)

# Create a custom registry
registry = CollectorRegistry()

# All metrics (comprehensive set)
system_cpu_usage = Gauge('system_cpu_usage_percent', 'System CPU usage percentage', registry=registry)
system_memory_total = Gauge('system_memory_total_bytes', 'Total system memory', registry=registry)
system_memory_used = Gauge('system_memory_used_bytes', 'Used system memory', registry=registry)
system_memory_available = Gauge('system_memory_available_bytes', 'Available system memory', registry=registry)
system_disk_total = Gauge('system_disk_total_bytes', 'Total disk space', ['device', 'mountpoint'], registry=registry)
system_disk_used = Gauge('system_disk_used_bytes', 'Used disk space', ['device', 'mountpoint'], registry=registry)
system_disk_free = Gauge('system_disk_free_bytes', 'Free disk space', ['device', 'mountpoint'], registry=registry)
system_network_rx = Gauge('system_network_receive_bytes_total', 'Network bytes received', ['interface'], registry=registry)
system_network_tx = Gauge('system_network_transmit_bytes_total', 'Network bytes transmitted', ['interface'], registry=registry)
system_load_1m = Gauge('system_load_1m', 'System load average 1 minute', registry=registry)
system_load_5m = Gauge('system_load_5m', 'System load average 5 minutes', registry=registry)
system_load_15m = Gauge('system_load_15m', 'System load average 15 minutes', registry=registry)
system_uptime = Gauge('system_uptime_seconds', 'System uptime in seconds', registry=registry)

# Process metrics
process_count = Gauge('process_count', 'Number of processes', ['name'], registry=registry)
process_cpu_usage = Gauge('process_cpu_usage_percent', 'Process CPU usage', ['name', 'pid'], registry=registry)
process_memory_usage = Gauge('process_memory_usage_bytes', 'Process memory usage', ['name', 'pid'], registry=registry)

# Docker container metrics  
docker_cpu_usage = Gauge('docker_container_cpu_usage_percent', 'Container CPU usage percentage', ['container_name', 'container_id', 'project'], registry=registry)
docker_memory_usage = Gauge('docker_container_memory_usage_bytes', 'Container memory usage in bytes', ['container_name', 'container_id', 'project'], registry=registry)
docker_memory_limit = Gauge('docker_container_memory_limit_bytes', 'Container memory limit in bytes', ['container_name', 'container_id', 'project'], registry=registry)
docker_network_rx = Gauge('docker_container_network_rx_bytes', 'Container network received bytes', ['container_name', 'container_id', 'project'], registry=registry)
docker_network_tx = Gauge('docker_container_network_tx_bytes', 'Container network transmitted bytes', ['container_name', 'container_id', 'project'], registry=registry)
docker_status = Gauge('docker_container_status', 'Container status (1=running, 0=other)', ['container_name', 'container_id', 'project', 'status'], registry=registry)

# GPU metrics
gpu_memory_total = Gauge('gpu_memory_total_bytes', 'Total GPU memory in bytes', ['gpu_index'], registry=registry)
gpu_memory_used = Gauge('gpu_memory_used_bytes', 'Used GPU memory in bytes', ['gpu_index'], registry=registry)
gpu_memory_known = Gauge('gpu_memory_known_bytes', 'GPU memory used by known processes', ['gpu_index'], registry=registry)
gpu_memory_unknown = Gauge('gpu_memory_unknown_bytes', 'GPU memory used by unknown processes', ['gpu_index'], registry=registry)
gpu_utilization = Gauge('gpu_utilization_percent', 'GPU utilization percentage', ['gpu_index'], registry=registry)
gpu_temperature = Gauge('gpu_temperature_celsius', 'GPU temperature in Celsius', ['gpu_index'], registry=registry)
gpu_power_usage = Gauge('gpu_power_usage_watts', 'GPU power usage in watts', ['gpu_index'], registry=registry)
container_gpu_memory_bytes = Gauge('container_gpu_memory_bytes', 'GPU memory usage by container', ['container_name', 'container_id', 'gpu_index', 'method'], registry=registry)
gpu_inference_active = Gauge('gpu_inference_active', 'Whether GPU inference detected unknown memory usage', ['gpu_index'], registry=registry)

# Vector DB and service health metrics
vector_db_up = Gauge('vector_db_up', 'Vector database availability', ['db_type', 'host'], registry=registry)
vector_db_response_time = Gauge('vector_db_response_time_seconds', 'Vector database response time', ['db_type', 'host', 'operation'], registry=registry)
service_up = Gauge('service_up', 'Service availability', ['service', 'endpoint'], registry=registry)
service_response_time = Gauge('service_response_time_seconds', 'Service response time', ['service', 'endpoint'], registry=registry)

# AURA self-monitoring
aura_component_up = Gauge('aura_component_up', 'AURA component status', ['component'], registry=registry)
aura_metrics_collected = Counter('aura_metrics_collected_total', 'Total metrics collected', ['type'], registry=registry)
aura_collection_duration = Histogram('aura_collection_duration_seconds', 'Time spent collecting metrics', ['type'], registry=registry)

# Global data store for web UI
metrics_data = {
    'system': {},
    'docker': {},
    'gpu': {},
    'services': {},
    'last_update': None
}

# Global historical data store
historical_data = HistoricalData()

class AuraMegaExporter:
    def __init__(self):
        self.gpu_count = 0
        if gpu_available:
            try:
                self.gpu_count = pynvml.nvmlDeviceGetCount()
                logger.info(f"Found {self.gpu_count} GPU(s)")
            except:
                self.gpu_count = 0
        
        self.container_gpu_memory = {}
        self.last_total_memory = {}
        
    def collect_system_metrics(self):
        """Collect comprehensive system metrics"""
        try:
            with aura_collection_duration.labels(type='system').time():
                # CPU metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                system_cpu_usage.set(cpu_percent)
                
                # Memory metrics
                memory = psutil.virtual_memory()
                system_memory_total.set(memory.total)
                system_memory_used.set(memory.used)
                system_memory_available.set(memory.available)
                
                # Disk metrics
                disk_data = []
                for partition in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        system_disk_total.labels(device=partition.device, mountpoint=partition.mountpoint).set(usage.total)
                        system_disk_used.labels(device=partition.device, mountpoint=partition.mountpoint).set(usage.used)
                        system_disk_free.labels(device=partition.device, mountpoint=partition.mountpoint).set(usage.free)
                        disk_data.append({
                            'device': partition.device,
                            'mountpoint': partition.mountpoint,
                            'total': usage.total,
                            'used': usage.used,
                            'free': usage.free
                        })
                    except PermissionError:
                        pass
                
                # Network metrics
                network = psutil.net_io_counters(pernic=True)
                network_data = []
                for interface, stats in network.items():
                    system_network_rx.labels(interface=interface).set(stats.bytes_recv)
                    system_network_tx.labels(interface=interface).set(stats.bytes_sent)
                    network_data.append({
                        'interface': interface,
                        'rx_bytes': stats.bytes_recv,
                        'tx_bytes': stats.bytes_sent
                    })
                
                # Load averages
                load1, load5, load15 = 0, 0, 0
                if hasattr(os, 'getloadavg'):
                    load1, load5, load15 = os.getloadavg()
                    system_load_1m.set(load1)
                    system_load_5m.set(load5)
                    system_load_15m.set(load15)
                
                # Uptime
                uptime = time.time() - psutil.boot_time()
                system_uptime.set(uptime)
                
                # Store for web UI
                metrics_data['system'] = {
                    'cpu_percent': cpu_percent,
                    'memory': {
                        'total': memory.total,
                        'used': memory.used,
                        'available': memory.available,
                        'percent': memory.percent
                    },
                    'disk': disk_data,
                    'network': network_data,
                    'load': {'1m': load1, '5m': load5, '15m': load15},
                    'uptime': uptime
                }
                
                aura_metrics_collected.labels(type='system').inc()
                
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def collect_docker_stats(self):
        """Collect Docker container statistics"""
        if not docker_client:
            return
            
        try:
            with aura_collection_duration.labels(type='docker').time():
                containers = docker_client.containers.list()
                container_data = []
                
                for container in containers:
                    try:
                        stats = container.stats(stream=False)
                        container_id = container.id[:12]
                        container_name = container.name
                        project = container.labels.get('project', 'unknown')
                        
                        # Calculate CPU percentage
                        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
                        system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
                        number_cpus = len(stats['cpu_stats']['cpu_usage'].get('percpu_usage', [])) or 1
                        
                        cpu_percent = 0
                        if system_cpu_delta > 0 and cpu_delta > 0:
                            cpu_percent = (cpu_delta / system_cpu_delta) * number_cpus * 100.0
                            docker_cpu_usage.labels(container_name=container_name, container_id=container_id, project=project).set(cpu_percent)
                        
                        # Memory stats
                        memory_usage = stats['memory_stats'].get('usage', 0)
                        memory_limit = stats['memory_stats'].get('limit', 0)
                        docker_memory_usage.labels(container_name=container_name, container_id=container_id, project=project).set(memory_usage)
                        docker_memory_limit.labels(container_name=container_name, container_id=container_id, project=project).set(memory_limit)
                        
                        # Network stats
                        networks = stats.get('networks', {})
                        total_rx = sum(net.get('rx_bytes', 0) for net in networks.values())
                        total_tx = sum(net.get('tx_bytes', 0) for net in networks.values())
                        docker_network_rx.labels(container_name=container_name, container_id=container_id, project=project).set(total_rx)
                        docker_network_tx.labels(container_name=container_name, container_id=container_id, project=project).set(total_tx)
                        
                        # Status
                        docker_status.labels(container_name=container_name, container_id=container_id, project=project, status=container.status).set(1 if container.status == 'running' else 0)
                        
                        container_data.append({
                            'name': container_name,
                            'id': container_id,
                            'project': project,
                            'status': container.status,
                            'cpu_percent': cpu_percent,
                            'memory_usage': memory_usage,
                            'memory_limit': memory_limit,
                            'network_rx': total_rx,
                            'network_tx': total_tx
                        })
                        
                    except Exception as e:
                        logger.error(f"Error collecting stats for container {container.name}: {e}")
                
                metrics_data['docker'] = container_data
                aura_metrics_collected.labels(type='docker').inc()
                        
        except Exception as e:
            logger.error(f"Error collecting Docker stats: {e}")
    
    def collect_gpu_metrics(self):
        """Collect comprehensive GPU metrics"""
        if not gpu_available or self.gpu_count == 0:
            return
            
        try:
            with aura_collection_duration.labels(type='gpu').time():
                gpu_data = []
                
                for gpu_idx in range(self.gpu_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_idx)
                    
                    # Basic GPU info
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    gpu_memory_total.labels(gpu_index=str(gpu_idx)).set(mem_info.total)
                    gpu_memory_used.labels(gpu_index=str(gpu_idx)).set(mem_info.used)
                    
                    # GPU utilization
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_utilization.labels(gpu_index=str(gpu_idx)).set(util.gpu)
                    
                    # Temperature
                    temp = 0
                    try:
                        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                        gpu_temperature.labels(gpu_index=str(gpu_idx)).set(temp)
                    except:
                        pass
                    
                    # Power usage
                    power = 0
                    try:
                        power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert mW to W
                        gpu_power_usage.labels(gpu_index=str(gpu_idx)).set(power)
                    except:
                        pass
                    
                    # Process inference
                    known_memory = 0
                    unknown_memory = 0
                    inference_active = False
                    try:
                        processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                        known_memory = sum(p.usedGpuMemory for p in processes)
                        gpu_memory_known.labels(gpu_index=str(gpu_idx)).set(known_memory)
                        
                        unknown_memory = max(0, mem_info.used - known_memory)
                        gpu_memory_unknown.labels(gpu_index=str(gpu_idx)).set(unknown_memory)
                        
                        if unknown_memory > 100 * 1024 * 1024:  # > 100MB
                            inference_active = True
                            gpu_inference_active.labels(gpu_index=str(gpu_idx)).set(1)
                        else:
                            gpu_inference_active.labels(gpu_index=str(gpu_idx)).set(0)
                            
                    except Exception as e:
                        logger.error(f"Error in GPU process inference: {e}")
                    
                    gpu_data.append({
                        'index': gpu_idx,
                        'memory_total': mem_info.total,
                        'memory_used': mem_info.used,
                        'memory_known': known_memory,
                        'memory_unknown': unknown_memory,
                        'utilization': util.gpu,
                        'temperature': temp,
                        'power': power,
                        'inference_active': inference_active
                    })
                
                metrics_data['gpu'] = gpu_data
                aura_metrics_collected.labels(type='gpu').inc()
                
        except Exception as e:
            logger.error(f"Error collecting GPU metrics: {e}")
    
    def collect_service_health(self):
        """Collect service health metrics"""
        try:
            with aura_collection_duration.labels(type='health').time():
                services = [
                    {'name': 'vector_db_chromadb', 'url': 'http://host.docker.internal:8000/api/v1/heartbeat'},
                    {'name': 'vector_db_qdrant', 'url': 'http://host.docker.internal:6333/'},
                    {'name': 'vector_db_weaviate', 'url': 'http://host.docker.internal:8081/v1/.well-known/ready'},
                ]
                
                service_data = []
                for svc in services:
                    try:
                        start_time = time.time()
                        response = requests.get(svc['url'], timeout=5)
                        response_time = time.time() - start_time
                        
                        is_up = response.status_code == 200
                        service_up.labels(service=svc['name'], endpoint=svc['url']).set(1 if is_up else 0)
                        
                        if is_up:
                            service_response_time.labels(service=svc['name'], endpoint=svc['url']).set(response_time)
                            
                            # Vector DB specific metrics
                            if 'vector_db' in svc['name']:
                                db_type = svc['name'].replace('vector_db_', '')
                                host = svc['url'].split('://')[1].split(':')[0]
                                vector_db_up.labels(db_type=db_type, host=host).set(1)
                                vector_db_response_time.labels(db_type=db_type, host=host, operation='health_check').set(response_time)
                        
                        service_data.append({
                            'name': svc['name'],
                            'url': svc['url'],
                            'status': 'up' if is_up else 'down',
                            'response_time': response_time if is_up else None
                        })
                            
                    except Exception as e:
                        service_up.labels(service=svc['name'], endpoint=svc['url']).set(0)
                        service_data.append({
                            'name': svc['name'],
                            'url': svc['url'],
                            'status': 'down',
                            'response_time': None,
                            'error': str(e)
                        })
                        logger.debug(f"Service {svc['name']} health check failed: {e}")
                
                metrics_data['services'] = service_data
                aura_metrics_collected.labels(type='health').inc()
                
        except Exception as e:
            logger.error(f"Error collecting service health: {e}")
    
    def collect_aura_self_metrics(self):
        """Collect AURA self-monitoring metrics"""
        try:
            # Mark our mega exporter as up
            aura_component_up.labels(component='mega_exporter').set(1)
            aura_component_up.labels(component='web_ui').set(1)
            aura_component_up.labels(component='embedded_prometheus').set(1)
                
        except Exception as e:
            logger.error(f"Error collecting AURA self metrics: {e}")
    
    def collect_all_metrics(self):
        """Collect all metrics in parallel"""
        logger.info("Collecting all metrics...")
        
        # Collect metrics in parallel using threads
        threads = [
            threading.Thread(target=self.collect_system_metrics),
            threading.Thread(target=self.collect_docker_stats),
            threading.Thread(target=self.collect_gpu_metrics),
            threading.Thread(target=self.collect_service_health),
            threading.Thread(target=self.collect_aura_self_metrics),
        ]
        
        for thread in threads:
            thread.start()
            
        for thread in threads:
            thread.join()
            
        metrics_data['last_update'] = datetime.now()
        
        # Update historical data
        update_historical_data(metrics_data, historical_data)
        
        logger.info("Metrics collection complete")
    
    def start_collection_loop(self):
        """Background thread for metric collection"""
        interval = int(os.environ.get('COLLECTION_INTERVAL', '15'))
        
        while True:
            try:
                self.collect_all_metrics()
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                time.sleep(interval)

# Global exporter instance
exporter = AuraMegaExporter()

# Create enhanced dashboard routes
create_enhanced_dashboard_routes(app, metrics_data, historical_data)

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(registry), mimetype='text/plain')

@app.route('/api/metrics')
def api_metrics():
    """JSON API for metrics"""
    return jsonify(metrics_data)

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

def main():
    """Main function"""
    logger.info("Starting AURA Mega Exporter...")
    
    # Start metrics collection in background
    collection_thread = threading.Thread(target=exporter.start_collection_loop)
    collection_thread.daemon = True
    collection_thread.start()
    
    # Initial collection
    exporter.collect_all_metrics()
    
    # Start Flask web server
    port = int(os.environ.get('EXPORTER_PORT', '8080'))
    logger.info(f"Starting web server on port {port}")
    logger.info(f"Dashboard: http://localhost:{port}/")
    logger.info(f"Metrics: http://localhost:{port}/metrics")
    logger.info(f"API: http://localhost:{port}/api/metrics")
    
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
Unified AURA Exporter - Combines all custom metric collection into a single service
"""

import os
import time
import json
import subprocess
import threading
import logging
import requests
from datetime import datetime
from prometheus_client import start_http_server, Gauge, Counter, Info, generate_latest
from prometheus_client.core import CollectorRegistry
import pynvml
import docker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('unified-exporter')

# Initialize Docker client
docker_client = docker.from_env()

# Initialize NVIDIA ML
pynvml.nvmlInit()

# Create a custom registry
registry = CollectorRegistry()

# Docker Stats Metrics
docker_cpu_usage = Gauge('docker_container_cpu_usage_percent', 'Container CPU usage percentage', ['container_name', 'container_id', 'project'], registry=registry)
docker_memory_usage = Gauge('docker_container_memory_usage_bytes', 'Container memory usage in bytes', ['container_name', 'container_id', 'project'], registry=registry)
docker_memory_limit = Gauge('docker_container_memory_limit_bytes', 'Container memory limit in bytes', ['container_name', 'container_id', 'project'], registry=registry)
docker_network_rx = Gauge('docker_container_network_rx_bytes', 'Container network received bytes', ['container_name', 'container_id', 'project'], registry=registry)
docker_network_tx = Gauge('docker_container_network_tx_bytes', 'Container network transmitted bytes', ['container_name', 'container_id', 'project'], registry=registry)
docker_block_read = Gauge('docker_container_block_read_bytes', 'Container block device read bytes', ['container_name', 'container_id', 'project'], registry=registry)
docker_block_write = Gauge('docker_container_block_write_bytes', 'Container block device write bytes', ['container_name', 'container_id', 'project'], registry=registry)
docker_pids = Gauge('docker_container_pids_current', 'Number of PIDs in container', ['container_name', 'container_id', 'project'], registry=registry)
docker_status = Gauge('docker_container_status', 'Container status (1=running, 0=other)', ['container_name', 'container_id', 'project', 'status'], registry=registry)
docker_restart_count = Gauge('docker_container_restart_count', 'Container restart count', ['container_name', 'container_id', 'project'], registry=registry)

# Container Label Info - removed due to serialization issues with complex dicts

# GPU Metrics (from nvidia-smi)
docker_gpu_usage = Gauge('docker_container_gpu_usage_percent', 'Container GPU usage percentage', ['container_name', 'container_id', 'project', 'gpu_index'], registry=registry)
docker_gpu_memory = Gauge('docker_container_gpu_memory_bytes', 'Container GPU memory usage in bytes', ['container_name', 'container_id', 'project', 'gpu_index'], registry=registry)

# GPU Inference Metrics
gpu_memory_total = Gauge('gpu_memory_total_bytes', 'Total GPU memory in bytes', ['gpu_index'], registry=registry)
gpu_memory_used = Gauge('gpu_memory_used_bytes', 'Used GPU memory in bytes', ['gpu_index'], registry=registry)
gpu_memory_known = Gauge('gpu_memory_known_bytes', 'GPU memory used by known processes', ['gpu_index'], registry=registry)
gpu_memory_unknown = Gauge('gpu_memory_unknown_bytes', 'GPU memory used by unknown processes', ['gpu_index'], registry=registry)
container_gpu_memory_bytes = Gauge('container_gpu_memory_bytes', 'GPU memory usage by container', ['container_name', 'container_id', 'gpu_index', 'method'], registry=registry)
gpu_inference_active = Gauge('gpu_inference_active', 'Whether GPU inference detected unknown memory usage', ['gpu_index'], registry=registry)

# Vector DB Metrics
vector_db_up = Gauge('vector_db_up', 'Vector database availability', ['db_type', 'host'], registry=registry)
vector_db_response_time = Gauge('vector_db_response_time_seconds', 'Vector database response time', ['db_type', 'host', 'operation'], registry=registry)
vector_db_collection_size = Gauge('vector_db_collection_size', 'Number of vectors in collection', ['db_type', 'host', 'collection'], registry=registry)
vector_db_embeddings_total = Counter('vector_db_embeddings_generated_total', 'Total embeddings generated', ['db_type', 'host'], registry=registry)
vector_db_searches_total = Counter('vector_db_similarity_searches_total', 'Total similarity searches', ['db_type', 'host'], registry=registry)
vector_db_insertions_total = Counter('vector_db_insertions_total', 'Total vector insertions', ['db_type', 'host'], registry=registry)
vector_db_memory = Gauge('vector_db_index_memory_bytes', 'Memory used by vector index', ['db_type', 'host'], registry=registry)
vector_db_connections = Gauge('vector_db_active_connections', 'Active database connections', ['db_type', 'host'], registry=registry)
vector_db_cache_hit_rate = Gauge('vector_db_cache_hit_rate', 'Cache hit rate', ['db_type', 'host'], registry=registry)
vector_db_errors = Counter('vector_db_operations_errors_total', 'Total operation errors', ['db_type', 'host', 'operation'], registry=registry)

# Ollama Metrics
ollama_up = Gauge('ollama_up', 'Ollama service availability', ['host'], registry=registry)
ollama_model_count = Gauge('ollama_model_count', 'Number of loaded models', ['host'], registry=registry)
ollama_model_size = Gauge('ollama_model_size_bytes', 'Size of loaded model in bytes', ['host', 'model'], registry=registry)
ollama_response_time = Gauge('ollama_api_response_time_seconds', 'Ollama API response time', ['host', 'endpoint'], registry=registry)
ollama_errors = Counter('ollama_api_errors_total', 'Total API errors', ['host', 'endpoint'], registry=registry)
ollama_inference_active = Gauge('ollama_inference_active', 'Whether inference is currently running', ['host'], registry=registry)
ollama_last_inference = Gauge('ollama_last_inference_timestamp', 'Timestamp of last inference', ['host'], registry=registry)


class UnifiedExporter:
    def __init__(self):
        self.gpu_count = pynvml.nvmlDeviceGetCount()
        self.container_gpu_memory = {}  # Track GPU memory per container
        self.last_total_memory = {}  # Track last total memory per GPU
        
    def get_container_labels(self):
        """Get all container labels for mapping"""
        try:
            containers = docker_client.containers.list(all=True)
            label_map = {}
            
            for container in containers:
                project = container.labels.get('project', 'unknown')
                label_map[container.id[:12]] = {
                    'name': container.name,
                    'project': project,
                    'labels': container.labels
                }
                
            return label_map
        except Exception as e:
            logger.error(f"Error getting container labels: {e}")
            return {}
    
    def collect_docker_stats(self):
        """Collect Docker container statistics"""
        try:
            containers = docker_client.containers.list()
            label_map = self.get_container_labels()
            
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
                    
                    # Block I/O stats
                    blkio_stats = stats.get('blkio_stats', {}).get('io_service_bytes_recursive', [])
                    read_bytes = sum(stat['value'] for stat in blkio_stats if stat['op'] == 'Read')
                    write_bytes = sum(stat['value'] for stat in blkio_stats if stat['op'] == 'Write')
                    docker_block_read.labels(container_name=container_name, container_id=container_id, project=project).set(read_bytes)
                    docker_block_write.labels(container_name=container_name, container_id=container_id, project=project).set(write_bytes)
                    
                    # PIDs
                    pids_current = stats.get('pids_stats', {}).get('current', 0)
                    docker_pids.labels(container_name=container_name, container_id=container_id, project=project).set(pids_current)
                    
                    # Status
                    docker_status.labels(container_name=container_name, container_id=container_id, project=project, status=container.status).set(1 if container.status == 'running' else 0)
                    
                    # Restart count
                    docker_restart_count.labels(container_name=container_name, container_id=container_id, project=project).set(container.attrs.get('RestartCount', 0))
                    
                except Exception as e:
                    logger.error(f"Error collecting stats for container {container.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error collecting Docker stats: {e}")
    
    def collect_gpu_metrics_nvidia_smi(self):
        """Collect GPU metrics using nvidia-smi (visible processes)"""
        try:
            # Get GPU process information
            cmd = "nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits"
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"nvidia-smi failed: {result.stderr}")
                return
            
            # Parse nvidia-smi output
            gpu_processes = {}
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                    
                parts = line.split(', ')
                if len(parts) >= 3:
                    pid = int(parts[0])
                    process_name = parts[1]
                    memory_mb = float(parts[2])
                    
                    # Find container for this PID
                    container_info = self.find_container_by_pid(pid)
                    if container_info:
                        container_id = container_info['id']
                        container_name = container_info['name']
                        project = container_info['project']
                        
                        # Note: nvidia-smi doesn't provide GPU index in this query
                        # For now, assume GPU 0 (can be enhanced with more complex parsing)
                        gpu_index = 0
                        
                        docker_gpu_memory.labels(
                            container_name=container_name,
                            container_id=container_id,
                            project=project,
                            gpu_index=str(gpu_index)
                        ).set(memory_mb * 1024 * 1024)  # Convert MB to bytes
                        
                        # Also update container_gpu_memory_bytes with method=nvidia-smi
                        container_gpu_memory_bytes.labels(
                            container_name=container_name,
                            container_id=container_id,
                            gpu_index=str(gpu_index),
                            method='nvidia-smi'
                        ).set(memory_mb * 1024 * 1024)
                        
        except Exception as e:
            logger.error(f"Error collecting GPU metrics via nvidia-smi: {e}")
    
    def collect_gpu_inference_metrics(self):
        """Collect GPU inference metrics (invisible processes)"""
        try:
            for gpu_idx in range(self.gpu_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_idx)
                
                # Get memory info
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                total_memory = mem_info.total
                used_memory = mem_info.used
                
                # Update basic GPU memory metrics
                gpu_memory_total.labels(gpu_index=str(gpu_idx)).set(total_memory)
                gpu_memory_used.labels(gpu_index=str(gpu_idx)).set(used_memory)
                
                # Get processes using this GPU
                try:
                    processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                    known_memory = sum(p.usedGpuMemory for p in processes)
                    gpu_memory_known.labels(gpu_index=str(gpu_idx)).set(known_memory)
                    
                    # Calculate unknown memory
                    unknown_memory = max(0, used_memory - known_memory)
                    gpu_memory_unknown.labels(gpu_index=str(gpu_idx)).set(unknown_memory)
                    
                    # Detect if there's significant unknown memory usage
                    if unknown_memory > 100 * 1024 * 1024:  # > 100MB
                        gpu_inference_active.labels(gpu_index=str(gpu_idx)).set(1)
                        
                        # Try to attribute to containers with GPU access
                        containers_with_gpu = self.find_containers_with_gpu_access()
                        if containers_with_gpu:
                            # Simple attribution: divide unknown memory among GPU containers without visible processes
                            containers_without_visible = []
                            
                            for container in containers_with_gpu:
                                has_visible_process = False
                                for process in processes:
                                    if self.pid_belongs_to_container(process.pid, container['id']):
                                        has_visible_process = True
                                        break
                                
                                if not has_visible_process:
                                    containers_without_visible.append(container)
                            
                            if containers_without_visible:
                                memory_per_container = unknown_memory / len(containers_without_visible)
                                
                                for container in containers_without_visible:
                                    container_gpu_memory_bytes.labels(
                                        container_name=container['name'],
                                        container_id=container['id'][:12],
                                        gpu_index=str(gpu_idx),
                                        method='inference'
                                    ).set(memory_per_container)
                    else:
                        gpu_inference_active.labels(gpu_index=str(gpu_idx)).set(0)
                        
                except pynvml.NVMLError as e:
                    logger.error(f"Error getting GPU processes: {e}")
                    
        except Exception as e:
            logger.error(f"Error collecting GPU inference metrics: {e}")
    
    def find_container_by_pid(self, pid):
        """Find container information by PID"""
        try:
            # Read the cgroup of the process from host proc
            proc_path = f'/host/proc/{pid}/cgroup'
            if not os.path.exists(proc_path):
                proc_path = f'/proc/{pid}/cgroup'
            
            with open(proc_path, 'r') as f:
                cgroup_content = f.read()
                
            # Look for docker container ID in cgroup
            for line in cgroup_content.split('\n'):
                if 'docker' in line:
                    parts = line.split('/')
                    for part in parts:
                        if len(part) == 64:  # Docker container ID length
                            container_id = part[:12]
                            
                            # Get container info
                            try:
                                container = docker_client.containers.get(container_id)
                                return {
                                    'id': container_id,
                                    'name': container.name,
                                    'project': container.labels.get('project', 'unknown')
                                }
                            except:
                                pass
                                
        except Exception:
            pass
            
        return None
    
    def find_containers_with_gpu_access(self):
        """Find containers that have GPU access"""
        containers_with_gpu = []
        
        try:
            containers = docker_client.containers.list()
            
            for container in containers:
                # Check if container has GPU access
                if container.attrs.get('HostConfig', {}).get('DeviceRequests'):
                    containers_with_gpu.append({
                        'id': container.id,
                        'name': container.name,
                        'project': container.labels.get('project', 'unknown')
                    })
                    
        except Exception as e:
            logger.error(f"Error finding containers with GPU access: {e}")
            
        return containers_with_gpu
    
    def pid_belongs_to_container(self, pid, container_id):
        """Check if a PID belongs to a specific container"""
        try:
            proc_path = f'/host/proc/{pid}/cgroup'
            if not os.path.exists(proc_path):
                proc_path = f'/proc/{pid}/cgroup'
                
            with open(proc_path, 'r') as f:
                cgroup_content = f.read()
                return container_id in cgroup_content
        except:
            return False
    
    def collect_vector_db_metrics(self):
        """Collect vector database metrics"""
        vector_dbs = [
            {'type': 'chromadb', 'host': 'host.docker.internal', 'port': 8000, 'endpoint': '/api/v1/heartbeat'},
            {'type': 'qdrant', 'host': 'host.docker.internal', 'port': 6333, 'endpoint': '/'},
            {'type': 'weaviate', 'host': 'host.docker.internal', 'port': 8081, 'endpoint': '/v1/.well-known/ready'},
        ]
        
        for db in vector_dbs:
            try:
                url = f"http://{db['host']}:{db['port']}{db['endpoint']}"
                start_time = time.time()
                
                response = requests.get(url, timeout=5)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    vector_db_up.labels(db_type=db['type'], host=db['host']).set(1)
                    vector_db_response_time.labels(db_type=db['type'], host=db['host'], operation='health_check').set(response_time)
                    
                    # Set placeholder metrics (these would be real in production)
                    vector_db_collection_size.labels(db_type=db['type'], host=db['host'], collection='default').set(1000)
                    vector_db_memory.labels(db_type=db['type'], host=db['host']).set(100 * 1024 * 1024)  # 100MB
                    vector_db_connections.labels(db_type=db['type'], host=db['host']).set(5)
                    vector_db_cache_hit_rate.labels(db_type=db['type'], host=db['host']).set(0.85)
                else:
                    vector_db_up.labels(db_type=db['type'], host=db['host']).set(0)
                    
            except Exception as e:
                vector_db_up.labels(db_type=db['type'], host=db['host']).set(0)
                vector_db_errors.labels(db_type=db['type'], host=db['host'], operation='health_check').inc()
                logger.error(f"Error checking {db['type']}: {e}")
    
    def collect_ollama_metrics(self):
        """Collect Ollama metrics"""
        ollama_host = os.environ.get('OLLAMA_HOST', 'host.docker.internal')
        ollama_port = os.environ.get('OLLAMA_PORT', '11434')
        
        try:
            # Check if Ollama is running
            url = f"http://{ollama_host}:{ollama_port}/api/tags"
            start_time = time.time()
            
            response = requests.get(url, timeout=5)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                ollama_up.labels(host=ollama_host).set(1)
                ollama_response_time.labels(host=ollama_host, endpoint='tags').set(response_time)
                
                # Parse models
                data = response.json()
                models = data.get('models', [])
                ollama_model_count.labels(host=ollama_host).set(len(models))
                
                for model in models:
                    model_name = model.get('name', 'unknown')
                    model_size = model.get('size', 0)
                    ollama_model_size.labels(host=ollama_host, model=model_name).set(model_size)
                    
                # Check if inference is active (this is a heuristic)
                # In a real implementation, you'd check actual inference status
                ollama_inference_active.labels(host=ollama_host).set(0)
                
            else:
                ollama_up.labels(host=ollama_host).set(0)
                
        except Exception as e:
            ollama_up.labels(host=ollama_host).set(0)
            ollama_errors.labels(host=ollama_host, endpoint='tags').inc()
            logger.error(f"Error checking Ollama: {e}")
    
    def collect_all_metrics(self):
        """Collect all metrics"""
        logger.info("Collecting all metrics...")
        
        # Collect metrics in parallel using threads
        threads = [
            threading.Thread(target=self.collect_docker_stats),
            threading.Thread(target=self.collect_gpu_metrics_nvidia_smi),
            threading.Thread(target=self.collect_gpu_inference_metrics),
            threading.Thread(target=self.collect_vector_db_metrics),
            threading.Thread(target=self.collect_ollama_metrics),
        ]
        
        for thread in threads:
            thread.start()
            
        for thread in threads:
            thread.join()
            
        logger.info("Metrics collection complete")
    
    def run(self):
        """Main run loop"""
        # Start HTTP server for Prometheus
        port = int(os.environ.get('EXPORTER_PORT', '9999'))
        start_http_server(port, registry=registry)
        logger.info(f"Unified exporter started on port {port}")
        
        # Collection interval
        interval = int(os.environ.get('COLLECTION_INTERVAL', '10'))
        
        while True:
            try:
                self.collect_all_metrics()
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Exporter stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(interval)


if __name__ == '__main__':
    exporter = UnifiedExporter()
    exporter.run()
#!/usr/bin/env python3
"""
GPU Memory Inference Exporter

This exporter uses a novel approach to detect GPU usage by containers that 
don't show up in nvidia-smi process lists (like Ollama).

Algorithm:
1. Get total GPU memory used
2. Enumerate all known GPU processes
3. Map known processes to containers
4. Calculate delta (total - known)
5. Assign delta to containers with GPU access but no visible processes
"""

import time
import subprocess
import json
import re
import os
import logging
from collections import defaultdict
from prometheus_client import Gauge, Counter, start_http_server
import pynvml

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
EXPORTER_PORT = int(os.environ.get('EXPORTER_PORT', '9201'))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', '10'))

# Metrics
gpu_memory_total_bytes = Gauge('gpu_memory_total_bytes', 'Total GPU memory in bytes', ['gpu'])
gpu_memory_used_bytes = Gauge('gpu_memory_used_bytes', 'Used GPU memory in bytes', ['gpu'])
gpu_memory_free_bytes = Gauge('gpu_memory_free_bytes', 'Free GPU memory in bytes', ['gpu'])
gpu_memory_known_bytes = Gauge('gpu_memory_known_bytes', 'GPU memory used by known processes', ['gpu'])
gpu_memory_unknown_bytes = Gauge('gpu_memory_unknown_bytes', 'GPU memory used by unknown processes', ['gpu'])

container_gpu_memory_bytes = Gauge('container_gpu_memory_bytes', 'GPU memory used by container', ['container_name', 'container_id', 'gpu', 'method'])
container_gpu_detected = Gauge('container_gpu_detected', 'Whether container has GPU access', ['container_name', 'container_id'])
gpu_inference_active = Gauge('gpu_inference_active', 'Whether GPU memory inference detected unknown usage', ['gpu'])

class GPUMemoryInference:
    def __init__(self):
        # Initialize NVML
        pynvml.nvmlInit()
        self.device_count = pynvml.nvmlDeviceGetCount()
        logger.info(f"Found {self.device_count} GPU(s)")
        
    def get_total_gpu_memory(self):
        """Get total GPU memory usage for all GPUs"""
        gpu_stats = {}
        
        for i in range(self.device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            
            gpu_stats[i] = {
                'total': mem_info.total,
                'used': mem_info.used,
                'free': mem_info.free
            }
            
            # Update metrics
            gpu_memory_total_bytes.labels(gpu=str(i)).set(mem_info.total)
            gpu_memory_used_bytes.labels(gpu=str(i)).set(mem_info.used)
            gpu_memory_free_bytes.labels(gpu=str(i)).set(mem_info.free)
            
        return gpu_stats
    
    def get_known_gpu_processes(self):
        """Get all known GPU processes using nvidia-smi"""
        known_processes = defaultdict(list)
        
        try:
            # Query compute processes
            cmd = ['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_gpu_memory', '--format=csv,noheader,nounits']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line and not line.startswith('[Not Supported]'):
                        parts = line.split(', ')
                        if len(parts) >= 3:
                            pid = int(parts[0])
                            gpu_uuid = parts[1]
                            memory_mb = float(parts[2])
                            
                            # Get GPU index from UUID
                            gpu_index = self._get_gpu_index_from_uuid(gpu_uuid)
                            
                            known_processes[gpu_index].append({
                                'pid': pid,
                                'memory_bytes': memory_mb * 1024 * 1024
                            })
                            
        except Exception as e:
            logger.error(f"Error getting GPU processes: {e}")
            
        return known_processes
    
    def _get_gpu_index_from_uuid(self, uuid):
        """Convert GPU UUID to index"""
        for i in range(self.device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            gpu_uuid = pynvml.nvmlDeviceGetUUID(handle).decode()
            if uuid in gpu_uuid:
                return i
        return 0
    
    def map_pid_to_container(self, pid):
        """Map a PID to a Docker container"""
        try:
            # Check cgroup for container ID
            with open(f'/proc/{pid}/cgroup', 'r') as f:
                cgroup_content = f.read()
                
            # Extract container ID from cgroup
            match = re.search(r'docker[/-]([a-f0-9]{64})', cgroup_content)
            if match:
                container_id = match.group(1)[:12]
                
                # Get container details
                cmd = ['docker', 'inspect', container_id]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    data = json.loads(result.stdout)[0]
                    return {
                        'id': container_id,
                        'name': data['Name'].lstrip('/'),
                        'labels': data['Config']['Labels']
                    }
                    
        except Exception as e:
            logger.debug(f"Could not map PID {pid} to container: {e}")
            
        return None
    
    def get_containers_with_gpu_access(self):
        """Get all containers that have GPU access"""
        containers = []
        
        try:
            # Get all running containers
            cmd = ['docker', 'ps', '--format', 'json']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        container_info = json.loads(line)
                        container_id = container_info['ID']
                        
                        # Check if container has GPU access
                        inspect_cmd = ['docker', 'inspect', container_id]
                        inspect_result = subprocess.run(inspect_cmd, capture_output=True, text=True)
                        
                        if inspect_result.returncode == 0:
                            data = json.loads(inspect_result.stdout)[0]
                            
                            has_gpu = False
                            
                            # Check for nvidia runtime
                            if data['HostConfig'].get('Runtime') == 'nvidia':
                                has_gpu = True
                            
                            # Check for GPU device requests
                            device_requests = data['HostConfig'].get('DeviceRequests', [])
                            for req in device_requests:
                                if req.get('Driver') == 'nvidia':
                                    has_gpu = True
                                    
                            # Check for NVIDIA environment variables
                            env_vars = data['Config'].get('Env', [])
                            for env in env_vars:
                                if env.startswith('NVIDIA_VISIBLE_DEVICES=') and \
                                   env not in ['NVIDIA_VISIBLE_DEVICES=none', 'NVIDIA_VISIBLE_DEVICES=void']:
                                    has_gpu = True
                                    
                            if has_gpu:
                                containers.append({
                                    'id': container_id[:12],
                                    'name': data['Name'].lstrip('/'),
                                    'labels': data['Config']['Labels'],
                                    'runtime': data['HostConfig'].get('Runtime', 'unknown')
                                })
                                
        except Exception as e:
            logger.error(f"Error getting containers with GPU access: {e}")
            
        return containers
    
    def calculate_inference(self):
        """Main inference calculation"""
        # Get total GPU memory usage
        gpu_stats = self.get_total_gpu_memory()
        
        # Get known GPU processes
        known_processes = self.get_known_gpu_processes()
        
        # Calculate known memory usage per GPU
        known_memory_per_gpu = {}
        container_memory_usage = defaultdict(lambda: defaultdict(int))
        
        for gpu_idx, processes in known_processes.items():
            known_memory = 0
            
            for proc in processes:
                known_memory += proc['memory_bytes']
                
                # Try to map to container
                container = self.map_pid_to_container(proc['pid'])
                if container:
                    container_memory_usage[container['id']][gpu_idx] += proc['memory_bytes']
                    
                    # Record known container usage
                    container_gpu_memory_bytes.labels(
                        container_name=container['name'],
                        container_id=container['id'],
                        gpu=str(gpu_idx),
                        method='nvidia-smi'
                    ).set(proc['memory_bytes'])
                    
            known_memory_per_gpu[gpu_idx] = known_memory
            gpu_memory_known_bytes.labels(gpu=str(gpu_idx)).set(known_memory)
        
        # Get containers with GPU access
        gpu_containers = self.get_containers_with_gpu_access()
        
        # Find containers with GPU access but no visible processes
        unknown_containers = []
        for container in gpu_containers:
            container_gpu_detected.labels(
                container_name=container['name'],
                container_id=container['id']
            ).set(1)
            
            if container['id'] not in container_memory_usage:
                unknown_containers.append(container)
                logger.info(f"Container {container['name']} has GPU access but no visible GPU processes")
        
        # Calculate unknown memory usage per GPU
        for gpu_idx in range(self.device_count):
            total_used = gpu_stats[gpu_idx]['used']
            known_used = known_memory_per_gpu.get(gpu_idx, 0)
            unknown_used = max(0, total_used - known_used)
            
            gpu_memory_unknown_bytes.labels(gpu=str(gpu_idx)).set(unknown_used)
            
            if unknown_used > 0:
                gpu_inference_active.labels(gpu=str(gpu_idx)).set(1)
                logger.info(f"GPU {gpu_idx}: {unknown_used / (1024**3):.2f} GB of unknown memory usage detected")
                
                # Distribute unknown memory among containers with GPU access but no processes
                if unknown_containers:
                    # Simple distribution: divide equally among unknown containers
                    # In production, you might use more sophisticated heuristics
                    per_container = unknown_used / len(unknown_containers)
                    
                    for container in unknown_containers:
                        container_gpu_memory_bytes.labels(
                            container_name=container['name'],
                            container_id=container['id'],
                            gpu=str(gpu_idx),
                            method='inference'
                        ).set(per_container)
                        
                        logger.info(f"Inferred {per_container / (1024**3):.2f} GB GPU memory for container {container['name']}")
            else:
                gpu_inference_active.labels(gpu=str(gpu_idx)).set(0)
    
    def cleanup(self):
        """Cleanup NVML"""
        try:
            pynvml.nvmlShutdown()
        except:
            pass

def main():
    """Main function"""
    logger.info(f"Starting GPU Memory Inference Exporter on port {EXPORTER_PORT}")
    
    # Start HTTP server
    start_http_server(EXPORTER_PORT)
    logger.info(f"Metrics available at http://localhost:{EXPORTER_PORT}/metrics")
    
    # Create inference engine
    inference = GPUMemoryInference()
    
    try:
        while True:
            try:
                inference.calculate_inference()
            except Exception as e:
                logger.error(f"Error in inference calculation: {e}")
                
            time.sleep(SCRAPE_INTERVAL)
            
    except KeyboardInterrupt:
        logger.info("Exporter stopped by user")
    finally:
        inference.cleanup()

if __name__ == "__main__":
    main()
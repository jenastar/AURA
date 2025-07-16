#!/usr/bin/env python3
"""
Enhanced GPU Memory Inference Exporter

Improvements:
- Smarter distribution based on container characteristics
- Historical tracking for better inference
- Detection of specific workload patterns
"""

import time
import subprocess
import json
import re
import os
import logging
from collections import defaultdict, deque
from datetime import datetime
from prometheus_client import Gauge, Counter, Histogram, start_http_server
import pynvml

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
EXPORTER_PORT = int(os.environ.get('EXPORTER_PORT', '9201'))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', '10'))
HISTORY_SIZE = int(os.environ.get('HISTORY_SIZE', '30'))

# Metrics
gpu_memory_total_bytes = Gauge('gpu_memory_total_bytes', 'Total GPU memory in bytes', ['gpu'])
gpu_memory_used_bytes = Gauge('gpu_memory_used_bytes', 'Used GPU memory in bytes', ['gpu'])
gpu_memory_free_bytes = Gauge('gpu_memory_free_bytes', 'Free GPU memory in bytes', ['gpu'])
gpu_memory_known_bytes = Gauge('gpu_memory_known_bytes', 'GPU memory used by known processes', ['gpu'])
gpu_memory_unknown_bytes = Gauge('gpu_memory_unknown_bytes', 'GPU memory used by unknown processes', ['gpu'])

container_gpu_memory_bytes = Gauge('container_gpu_memory_bytes', 'GPU memory used by container', 
                                  ['container_name', 'container_id', 'gpu', 'method'])
container_gpu_score = Gauge('container_gpu_score', 'GPU likelihood score for container', 
                           ['container_name', 'container_id'])
container_gpu_detected = Gauge('container_gpu_detected', 'Whether container has GPU access', 
                              ['container_name', 'container_id'])

gpu_inference_active = Gauge('gpu_inference_active', 'Whether GPU memory inference detected unknown usage', ['gpu'])
gpu_inference_confidence = Gauge('gpu_inference_confidence', 'Confidence level of GPU inference (0-1)', ['gpu'])

# Histograms for tracking patterns
unknown_memory_histogram = Histogram('gpu_unknown_memory_bytes_histogram', 'Distribution of unknown memory')

class ContainerProfile:
    """Profile for tracking container GPU behavior"""
    def __init__(self, container_id, container_name):
        self.container_id = container_id
        self.container_name = container_name
        self.gpu_history = deque(maxlen=HISTORY_SIZE)
        self.last_seen_with_gpu = None
        self.typical_memory = 0
        self.is_llm = self._detect_llm_container(container_name)
        
    def _detect_llm_container(self, name):
        """Detect if container is likely running an LLM"""
        llm_indicators = ['ollama', 'llama', 'gpt', 'llm', 'ai', 'ml', 'model', 'inference']
        name_lower = name.lower()
        return any(indicator in name_lower for indicator in llm_indicators)
    
    def update(self, has_visible_gpu, memory_bytes=0):
        """Update container profile with new observation"""
        self.gpu_history.append({
            'timestamp': time.time(),
            'visible': has_visible_gpu,
            'memory': memory_bytes
        })
        
        if has_visible_gpu:
            self.last_seen_with_gpu = time.time()
            
        # Calculate typical memory usage
        if len(self.gpu_history) > 5:
            visible_memories = [h['memory'] for h in self.gpu_history if h['visible'] and h['memory'] > 0]
            if visible_memories:
                self.typical_memory = sum(visible_memories) / len(visible_memories)
    
    def get_gpu_likelihood_score(self):
        """Calculate likelihood this container is using GPU"""
        score = 0.0
        
        # Base score for LLM containers
        if self.is_llm:
            score += 0.5
            
        # Recent GPU activity
        if self.last_seen_with_gpu:
            time_since_gpu = time.time() - self.last_seen_with_gpu
            if time_since_gpu < 300:  # 5 minutes
                score += 0.3 * (1 - time_since_gpu / 300)
                
        # Historical GPU usage pattern
        if len(self.gpu_history) > 10:
            gpu_count = sum(1 for h in self.gpu_history if h['visible'])
            score += 0.2 * (gpu_count / len(self.gpu_history))
            
        return min(score, 1.0)

class EnhancedGPUInference:
    def __init__(self):
        # Initialize NVML
        pynvml.nvmlInit()
        self.device_count = pynvml.nvmlDeviceGetCount()
        logger.info(f"Found {self.device_count} GPU(s)")
        
        # Container profiles
        self.container_profiles = {}
        
        # History tracking
        self.memory_history = defaultdict(lambda: deque(maxlen=HISTORY_SIZE))
        
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
            
            # Track history
            self.memory_history[i].append(mem_info.used)
            
        return gpu_stats
    
    def get_container_weight(self, container, unknown_containers):
        """Calculate weight for distributing unknown memory"""
        profile = self.container_profiles.get(container['id'])
        if not profile:
            # Create new profile
            profile = ContainerProfile(container['id'], container['name'])
            self.container_profiles[container['id']] = profile
            
        base_weight = 1.0
        
        # Adjust weight based on container characteristics
        if profile.is_llm:
            base_weight *= 2.0
            
        # Adjust based on GPU likelihood score
        likelihood = profile.get_gpu_likelihood_score()
        base_weight *= (1 + likelihood)
        
        # Update container score metric
        container_gpu_score.labels(
            container_name=container['name'],
            container_id=container['id']
        ).set(likelihood)
        
        return base_weight
    
    def distribute_unknown_memory(self, unknown_memory, unknown_containers, gpu_idx):
        """Intelligently distribute unknown memory among containers"""
        if not unknown_containers or unknown_memory <= 0:
            return
            
        # Calculate weights for each container
        weights = {}
        total_weight = 0
        
        for container in unknown_containers:
            weight = self.get_container_weight(container, unknown_containers)
            weights[container['id']] = weight
            total_weight += weight
            
        # Distribute memory proportionally
        for container in unknown_containers:
            if total_weight > 0:
                proportion = weights[container['id']] / total_weight
                allocated_memory = unknown_memory * proportion
                
                container_gpu_memory_bytes.labels(
                    container_name=container['name'],
                    container_id=container['id'],
                    gpu=str(gpu_idx),
                    method='inference'
                ).set(allocated_memory)
                
                logger.info(
                    f"Allocated {allocated_memory / (1024**3):.2f} GB to {container['name']} "
                    f"(weight: {weights[container['id']]:.2f})"
                )
    
    def calculate_inference_confidence(self, gpu_idx, unknown_memory, total_memory):
        """Calculate confidence level of inference"""
        if total_memory == 0:
            return 0.0
            
        unknown_ratio = unknown_memory / total_memory
        
        # Check if unknown memory follows a pattern
        history = list(self.memory_history[gpu_idx])
        if len(history) > 10:
            # Check for stability
            avg = sum(history) / len(history)
            variance = sum((x - avg) ** 2 for x in history) / len(history)
            stability = 1 / (1 + variance / (avg ** 2) if avg > 0 else 1)
            
            confidence = unknown_ratio * stability
        else:
            confidence = unknown_ratio * 0.5
            
        gpu_inference_confidence.labels(gpu=str(gpu_idx)).set(confidence)
        return confidence
    
    def calculate_inference(self):
        """Enhanced inference calculation"""
        # Get total GPU memory usage
        gpu_stats = self.get_total_gpu_memory()
        
        # Get known GPU processes
        known_processes = self.get_known_gpu_processes()
        
        # Get containers with GPU access
        gpu_containers = self.get_containers_with_gpu_access()
        
        # Update container profiles
        known_container_ids = set()
        
        # Process known GPU usage
        for gpu_idx, processes in known_processes.items():
            known_memory = 0
            
            for proc in processes:
                known_memory += proc['memory_bytes']
                
                # Map to container
                container = self.map_pid_to_container(proc['pid'])
                if container:
                    known_container_ids.add(container['id'])
                    
                    # Update profile
                    if container['id'] in self.container_profiles:
                        self.container_profiles[container['id']].update(True, proc['memory_bytes'])
                    
                    # Record known usage
                    container_gpu_memory_bytes.labels(
                        container_name=container['name'],
                        container_id=container['id'],
                        gpu=str(gpu_idx),
                        method='nvidia-smi'
                    ).set(proc['memory_bytes'])
                    
            gpu_memory_known_bytes.labels(gpu=str(gpu_idx)).set(known_memory)
        
        # Process each GPU
        for gpu_idx in range(self.device_count):
            total_used = gpu_stats[gpu_idx]['used']
            known_used = sum(p['memory_bytes'] for p in known_processes.get(gpu_idx, []))
            unknown_used = max(0, total_used - known_used)
            
            gpu_memory_unknown_bytes.labels(gpu=str(gpu_idx)).set(unknown_used)
            unknown_memory_histogram.observe(unknown_used)
            
            # Find unknown containers
            unknown_containers = []
            for container in gpu_containers:
                container_gpu_detected.labels(
                    container_name=container['name'],
                    container_id=container['id']
                ).set(1)
                
                if container['id'] not in known_container_ids:
                    unknown_containers.append(container)
                    
                    # Update profile for unknown containers
                    if container['id'] in self.container_profiles:
                        self.container_profiles[container['id']].update(False)
                        
            if unknown_used > 0:
                gpu_inference_active.labels(gpu=str(gpu_idx)).set(1)
                
                # Calculate confidence
                confidence = self.calculate_inference_confidence(
                    gpu_idx, unknown_used, total_used
                )
                
                logger.info(
                    f"GPU {gpu_idx}: {unknown_used / (1024**3):.2f} GB unknown memory "
                    f"(confidence: {confidence:.2%})"
                )
                
                # Distribute unknown memory
                self.distribute_unknown_memory(unknown_used, unknown_containers, gpu_idx)
            else:
                gpu_inference_active.labels(gpu=str(gpu_idx)).set(0)
                gpu_inference_confidence.labels(gpu=str(gpu_idx)).set(0)
    
    # Include other methods from original script (get_known_gpu_processes, map_pid_to_container, etc.)
    def get_known_gpu_processes(self):
        """Get all known GPU processes using nvidia-smi"""
        known_processes = defaultdict(list)
        
        try:
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
            with open(f'/host/proc/{pid}/cgroup', 'r') as f:
                cgroup_content = f.read()
                
            match = re.search(r'docker[/-]([a-f0-9]{64})', cgroup_content)
            if match:
                container_id = match.group(1)[:12]
                
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
            cmd = ['docker', 'ps', '--format', 'json']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        container_info = json.loads(line)
                        container_id = container_info['ID']
                        
                        inspect_cmd = ['docker', 'inspect', container_id]
                        inspect_result = subprocess.run(inspect_cmd, capture_output=True, text=True)
                        
                        if inspect_result.returncode == 0:
                            data = json.loads(inspect_result.stdout)[0]
                            
                            has_gpu = False
                            
                            if data['HostConfig'].get('Runtime') == 'nvidia':
                                has_gpu = True
                            
                            device_requests = data['HostConfig'].get('DeviceRequests', [])
                            for req in device_requests:
                                if req.get('Driver') == 'nvidia':
                                    has_gpu = True
                                    
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
    
    def cleanup(self):
        """Cleanup NVML"""
        try:
            pynvml.nvmlShutdown()
        except:
            pass

def main():
    """Main function"""
    logger.info(f"Starting Enhanced GPU Memory Inference Exporter on port {EXPORTER_PORT}")
    
    start_http_server(EXPORTER_PORT)
    logger.info(f"Metrics available at http://localhost:{EXPORTER_PORT}/metrics")
    
    inference = EnhancedGPUInference()
    
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
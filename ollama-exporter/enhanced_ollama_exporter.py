#!/usr/bin/env python3
"""
Enhanced Ollama Prometheus Exporter
Monitors Ollama API and attempts to detect GPU usage through inference tracking
"""

import time
import requests
import json
import threading
from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest
from prometheus_client import start_http_server
import os
import logging
from datetime import datetime
from collections import deque

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'ollama')
OLLAMA_PORT = os.environ.get('OLLAMA_PORT', '11434')
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
EXPORTER_PORT = int(os.environ.get('EXPORTER_PORT', '9200'))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', '5'))
INFERENCE_CHECK_INTERVAL = int(os.environ.get('INFERENCE_CHECK_INTERVAL', '2'))

# Metrics
ollama_up = Gauge('ollama_up', 'Whether Ollama API is accessible (1 = up, 0 = down)')
ollama_model_count = Gauge('ollama_model_count', 'Number of models available in Ollama')
ollama_model_info = Gauge('ollama_model_info', 'Model information', ['model', 'family', 'parameter_size', 'quantization'])
ollama_model_size_bytes = Gauge('ollama_model_size_bytes', 'Size of model in bytes', ['model'])

# API metrics
ollama_api_response_time = Histogram('ollama_api_response_time_seconds', 'API response time in seconds', ['endpoint'])
ollama_api_errors_total = Counter('ollama_api_errors_total', 'Total number of API errors', ['endpoint', 'error_type'])

# Inference detection metrics
ollama_inference_active = Gauge('ollama_inference_active', 'Whether inference is currently active (1 = yes, 0 = no)')
ollama_inference_requests_total = Counter('ollama_inference_requests_total', 'Total number of inference requests detected')
ollama_inference_duration = Summary('ollama_inference_duration_seconds', 'Duration of inference requests')
ollama_last_inference_timestamp = Gauge('ollama_last_inference_timestamp', 'Timestamp of last inference request')
ollama_gpu_likely_active = Gauge('ollama_gpu_likely_active', 'Likelihood that GPU is being used (0-1)')

# Container detection
ollama_container_detected = Gauge('ollama_container_detected', 'Whether Ollama container is detected', ['container_name'])

class InferenceDetector:
    """Detects when Ollama is performing inference"""
    
    def __init__(self):
        self.active_inferences = {}
        self.inference_history = deque(maxlen=10)  # Keep last 10 inference times
        self.lock = threading.Lock()
        self.last_model_activity = {}
        
    def check_inference(self):
        """Check if Ollama is currently performing inference"""
        try:
            # Method 1: Try to make a minimal generate request with timeout
            # If Ollama is busy, it might take longer to respond
            test_payload = {
                "model": "llama2:latest",  # Use a model that should exist
                "prompt": "",
                "stream": False,
                "options": {"num_predict": 1}  # Minimal generation
            }
            
            start_time = time.time()
            try:
                response = requests.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json=test_payload,
                    timeout=0.5  # Very short timeout
                )
                response_time = time.time() - start_time
                
                # If response is slow, inference might be active
                if response_time > 0.3:
                    self.mark_inference_active()
                    
            except requests.exceptions.Timeout:
                # Timeout likely means Ollama is busy with inference
                self.mark_inference_active()
            except Exception:
                pass
                
            # Method 2: Check model endpoint response times
            # Active models might respond differently
            try:
                start_time = time.time()
                response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=1)
                response_time = time.time() - start_time
                
                if response_time > 0.5:  # Slower than normal
                    self.mark_inference_likely_active(0.7)
                    
            except:
                pass
                
        except Exception as e:
            logger.debug(f"Error checking inference: {e}")
            
    def mark_inference_active(self):
        """Mark that inference is currently active"""
        with self.lock:
            current_time = time.time()
            self.inference_history.append(current_time)
            ollama_inference_active.set(1)
            ollama_gpu_likely_active.set(1)
            ollama_last_inference_timestamp.set(current_time)
            ollama_inference_requests_total.inc()
            logger.info("Inference detected as active")
            
    def mark_inference_likely_active(self, likelihood):
        """Mark likelihood of active inference"""
        with self.lock:
            ollama_gpu_likely_active.set(likelihood)
            
    def update_status(self):
        """Update inference status based on history"""
        with self.lock:
            current_time = time.time()
            
            # Check if any inference in last 30 seconds
            recent_inferences = [t for t in self.inference_history if current_time - t < 30]
            
            if recent_inferences:
                # Still consider active if recent
                ollama_inference_active.set(1)
                # GPU likelihood decreases over time
                time_since_last = current_time - max(recent_inferences)
                likelihood = max(0, 1 - (time_since_last / 30))
                ollama_gpu_likely_active.set(likelihood)
            else:
                ollama_inference_active.set(0)
                ollama_gpu_likely_active.set(0)

class OllamaMonitor:
    """Main monitoring class"""
    
    def __init__(self):
        self.inference_detector = InferenceDetector()
        
    def collect_metrics(self):
        """Collect all metrics from Ollama"""
        try:
            # Check if Ollama is up
            start_time = time.time()
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                ollama_up.set(1)
                ollama_api_response_time.labels(endpoint='tags').observe(response_time)
                
                # Parse model information
                data = response.json()
                models = data.get('models', [])
                ollama_model_count.set(len(models))
                
                # Track each model
                for model in models:
                    model_name = model.get('name', 'unknown')
                    model_size = model.get('size', 0)
                    details = model.get('details', {})
                    
                    ollama_model_size_bytes.labels(model=model_name).set(model_size)
                    
                    ollama_model_info.labels(
                        model=model_name,
                        family=details.get('family', 'unknown'),
                        parameter_size=details.get('parameter_size', 'unknown'),
                        quantization=details.get('quantization_level', 'unknown')
                    ).set(1)
                    
                logger.info(f"Collected metrics: {len(models)} models found")
                
            else:
                ollama_up.set(0)
                ollama_api_errors_total.labels(endpoint='tags', error_type='http_error').inc()
                
        except requests.exceptions.RequestException as e:
            ollama_up.set(0)
            ollama_api_errors_total.labels(endpoint='tags', error_type='connection_error').inc()
            logger.error(f"Failed to connect to Ollama API: {e}")
            
        # Update inference status
        self.inference_detector.update_status()
        
    def inference_check_loop(self):
        """Separate thread to check for active inference"""
        while True:
            try:
                self.inference_detector.check_inference()
            except Exception as e:
                logger.error(f"Error in inference check: {e}")
            time.sleep(INFERENCE_CHECK_INTERVAL)

def check_ollama_container():
    """Try to detect if we're monitoring the right Ollama container"""
    try:
        # Check if OLLAMA_HOST resolves to a container
        import socket
        ip = socket.gethostbyname(OLLAMA_HOST)
        # In Docker networks, containers typically get 172.x.x.x IPs
        if ip.startswith('172.'):
            ollama_container_detected.labels(container_name=OLLAMA_HOST).set(1)
            logger.info(f"Detected Ollama container at {ip}")
    except:
        ollama_container_detected.labels(container_name='unknown').set(0)

def main():
    """Main function"""
    logger.info(f"Starting Enhanced Ollama Prometheus Exporter on port {EXPORTER_PORT}")
    logger.info(f"Monitoring Ollama at {OLLAMA_BASE_URL}")
    
    # Check for Ollama container
    check_ollama_container()
    
    # Create monitor
    monitor = OllamaMonitor()
    
    # Start inference detection thread
    inference_thread = threading.Thread(target=monitor.inference_check_loop, daemon=True)
    inference_thread.start()
    
    # Start HTTP server
    start_http_server(EXPORTER_PORT)
    logger.info(f"Metrics available at http://localhost:{EXPORTER_PORT}/metrics")
    
    # Main metrics collection loop
    while True:
        try:
            monitor.collect_metrics()
        except KeyboardInterrupt:
            logger.info("Exporter stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            
        time.sleep(SCRAPE_INTERVAL)

if __name__ == "__main__":
    main()
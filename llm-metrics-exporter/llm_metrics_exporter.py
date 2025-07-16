#!/usr/bin/env python3
"""
LLM Metrics Exporter for Prometheus
Tracks tokens/sec, latency, token counts, model load time, and error rates
for LLM inference systems (Ollama, vLLM, etc.)
"""

import os
import time
import json
import threading
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from prometheus_client import (
    start_http_server, 
    Counter, 
    Gauge, 
    Histogram, 
    Summary,
    Info
)

# Metrics definitions
tokens_generated_total = Counter(
    'llm_tokens_generated_total',
    'Total number of tokens generated',
    ['model', 'container', 'endpoint']
)

prompt_tokens_total = Counter(
    'llm_prompt_tokens_total',
    'Total number of prompt tokens processed',
    ['model', 'container', 'endpoint']
)

response_tokens_total = Counter(
    'llm_response_tokens_total',
    'Total number of response tokens generated',
    ['model', 'container', 'endpoint']
)

inference_latency = Histogram(
    'llm_inference_latency_seconds',
    'Time taken to complete inference request',
    ['model', 'container', 'endpoint'],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, float('inf'))
)

tokens_per_second = Gauge(
    'llm_tokens_per_second',
    'Current tokens per second generation rate',
    ['model', 'container', 'endpoint']
)

active_requests = Gauge(
    'llm_active_requests',
    'Number of currently active inference requests',
    ['model', 'container', 'endpoint']
)

model_load_time = Gauge(
    'llm_model_load_time_seconds',
    'Time taken to load the model',
    ['model', 'container']
)

inference_errors = Counter(
    'llm_inference_errors_total',
    'Total number of inference errors',
    ['model', 'container', 'error_type']
)

model_info = Info(
    'llm_model',
    'Information about loaded models',
    ['model', 'container']
)

queue_size = Gauge(
    'llm_queue_size',
    'Number of requests waiting in queue',
    ['model', 'container', 'endpoint']
)

memory_usage_bytes = Gauge(
    'llm_memory_usage_bytes',
    'Memory usage of the LLM process',
    ['model', 'container', 'memory_type']
)

# Per-request tracking for accurate tokens/sec calculation
class RequestTracker:
    def __init__(self):
        self.active_requests: Dict[str, dict] = {}
        self.lock = threading.Lock()
        
    def start_request(self, request_id: str, model: str, container: str, endpoint: str):
        with self.lock:
            self.active_requests[request_id] = {
                'start_time': time.time(),
                'model': model,
                'container': container,
                'endpoint': endpoint,
                'tokens_generated': 0
            }
            active_requests.labels(model=model, container=container, endpoint=endpoint).inc()
    
    def update_tokens(self, request_id: str, tokens: int):
        with self.lock:
            if request_id in self.active_requests:
                self.active_requests[request_id]['tokens_generated'] += tokens
                # Calculate current tokens/sec
                elapsed = time.time() - self.active_requests[request_id]['start_time']
                if elapsed > 0:
                    tps = self.active_requests[request_id]['tokens_generated'] / elapsed
                    req = self.active_requests[request_id]
                    tokens_per_second.labels(
                        model=req['model'],
                        container=req['container'],
                        endpoint=req['endpoint']
                    ).set(tps)
    
    def end_request(self, request_id: str, prompt_tokens: int, response_tokens: int, error: Optional[str] = None):
        with self.lock:
            if request_id in self.active_requests:
                req = self.active_requests[request_id]
                elapsed = time.time() - req['start_time']
                
                # Update metrics
                if not error:
                    inference_latency.labels(
                        model=req['model'],
                        container=req['container'],
                        endpoint=req['endpoint']
                    ).observe(elapsed)
                    
                    tokens_generated_total.labels(
                        model=req['model'],
                        container=req['container'],
                        endpoint=req['endpoint']
                    ).inc(prompt_tokens + response_tokens)
                    
                    prompt_tokens_total.labels(
                        model=req['model'],
                        container=req['container'],
                        endpoint=req['endpoint']
                    ).inc(prompt_tokens)
                    
                    response_tokens_total.labels(
                        model=req['model'],
                        container=req['container'],
                        endpoint=req['endpoint']
                    ).inc(response_tokens)
                else:
                    inference_errors.labels(
                        model=req['model'],
                        container=req['container'],
                        error_type=error
                    ).inc()
                
                active_requests.labels(
                    model=req['model'],
                    container=req['container'],
                    endpoint=req['endpoint']
                ).dec()
                
                del self.active_requests[request_id]


class OllamaMetricsCollector:
    """Collector for Ollama-specific metrics"""
    
    def __init__(self, ollama_host: str, ollama_port: int):
        self.base_url = f"http://{ollama_host}:{ollama_port}"
        self.tracker = RequestTracker()
        self.container_name = os.environ.get('CONTAINER_NAME', 'ollama')
        
    def collect_metrics(self):
        """Collect metrics from Ollama API"""
        try:
            # Get loaded models
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                for model in models:
                    model_name = model.get('name', 'unknown')
                    model_info.labels(
                        model=model_name,
                        container=self.container_name
                    ).info({
                        'size': str(model.get('size', 0)),
                        'modified': model.get('modified_at', ''),
                        'family': model.get('details', {}).get('family', 'unknown')
                    })
                    
                    # Track model load time if available
                    if 'loaded_at' in model:
                        load_time = model.get('load_duration_seconds', 0)
                        model_load_time.labels(
                            model=model_name,
                            container=self.container_name
                        ).set(load_time)
            
            # Get running models and their memory usage
            ps_response = requests.get(f"{self.base_url}/api/ps", timeout=5)
            if ps_response.status_code == 200:
                processes = ps_response.json().get('models', [])
                for proc in processes:
                    model_name = proc.get('name', 'unknown')
                    vram_usage = proc.get('size', 0)
                    memory_usage_bytes.labels(
                        model=model_name,
                        container=self.container_name,
                        memory_type='vram'
                    ).set(vram_usage)
                    
        except requests.exceptions.RequestException as e:
            inference_errors.labels(
                model='unknown',
                container=self.container_name,
                error_type='connection_error'
            ).inc()
            print(f"Error collecting Ollama metrics: {e}")
    
    def track_inference(self, request_id: str, model: str, prompt: str, endpoint: str = '/api/generate'):
        """Track an inference request"""
        # This would be called by your inference wrapper
        self.tracker.start_request(request_id, model, self.container_name, endpoint)
        
    def update_streaming_tokens(self, request_id: str, tokens: int):
        """Update token count for streaming responses"""
        self.tracker.update_tokens(request_id, tokens)
        
    def complete_inference(self, request_id: str, prompt_tokens: int, response_tokens: int, error: Optional[str] = None):
        """Complete tracking for an inference request"""
        self.tracker.end_request(request_id, prompt_tokens, response_tokens, error)


class VLLMMetricsCollector:
    """Collector for vLLM-specific metrics"""
    
    def __init__(self, vllm_host: str, vllm_port: int):
        self.base_url = f"http://{vllm_host}:{vllm_port}"
        self.tracker = RequestTracker()
        self.container_name = os.environ.get('CONTAINER_NAME', 'vllm')
        
    def collect_metrics(self):
        """Collect metrics from vLLM metrics endpoint"""
        try:
            # vLLM exposes its own metrics at /metrics
            response = requests.get(f"{self.base_url}/metrics", timeout=5)
            if response.status_code == 200:
                # Parse vLLM native metrics and enhance them
                # This is where you'd parse vLLM's prometheus metrics
                # and add additional context
                pass
                
        except requests.exceptions.RequestException as e:
            inference_errors.labels(
                model='unknown',
                container=self.container_name,
                error_type='connection_error'
            ).inc()
            print(f"Error collecting vLLM metrics: {e}")


class GenericLLMMetricsCollector:
    """Generic collector that can work with any LLM API"""
    
    def __init__(self, api_endpoint: str, container_name: str):
        self.api_endpoint = api_endpoint
        self.tracker = RequestTracker()
        self.container_name = container_name
        
    def wrap_inference(self, inference_func, model: str, prompt: str, **kwargs):
        """Wrapper to track any inference function"""
        request_id = f"{model}_{int(time.time() * 1000000)}"
        self.tracker.start_request(request_id, model, self.container_name, self.api_endpoint)
        
        try:
            start_time = time.time()
            result = inference_func(prompt, **kwargs)
            
            # Extract token counts (adjust based on your API response format)
            prompt_tokens = kwargs.get('prompt_tokens', len(prompt.split()))
            response_tokens = kwargs.get('response_tokens', len(str(result).split()))
            
            self.tracker.end_request(request_id, prompt_tokens, response_tokens)
            return result
            
        except Exception as e:
            error_type = type(e).__name__
            self.tracker.end_request(request_id, 0, 0, error=error_type)
            raise


def main():
    # Configuration
    port = int(os.environ.get('EXPORTER_PORT', '9202'))
    scrape_interval = int(os.environ.get('SCRAPE_INTERVAL', '10'))
    
    # Determine which LLM system we're monitoring
    llm_type = os.environ.get('LLM_TYPE', 'ollama')
    
    # Initialize appropriate collector
    if llm_type == 'ollama':
        ollama_host = os.environ.get('OLLAMA_HOST', 'localhost')
        ollama_port = int(os.environ.get('OLLAMA_PORT', '11434'))
        collector = OllamaMetricsCollector(ollama_host, ollama_port)
    elif llm_type == 'vllm':
        vllm_host = os.environ.get('VLLM_HOST', 'localhost')
        vllm_port = int(os.environ.get('VLLM_PORT', '8000'))
        collector = VLLMMetricsCollector(vllm_host, vllm_port)
    else:
        # Generic collector
        api_endpoint = os.environ.get('LLM_API_ENDPOINT', 'http://localhost:8080')
        container_name = os.environ.get('CONTAINER_NAME', 'llm')
        collector = GenericLLMMetricsCollector(api_endpoint, container_name)
    
    # Start Prometheus metrics server
    start_http_server(port)
    print(f"LLM Metrics Exporter started on port {port}")
    print(f"Monitoring {llm_type} LLM system")
    
    # Continuous metrics collection
    while True:
        try:
            collector.collect_metrics()
        except Exception as e:
            print(f"Error in metrics collection: {e}")
        
        time.sleep(scrape_interval)


if __name__ == "__main__":
    main()
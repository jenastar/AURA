#!/usr/bin/env python3
"""
Ollama Prometheus Exporter
Monitors Ollama API and exports metrics for Prometheus
"""

import time
import requests
import json
from prometheus_client import Counter, Gauge, Histogram, generate_latest, REGISTRY
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, CollectorRegistry
from prometheus_client import start_http_server
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'ollama')
OLLAMA_PORT = os.environ.get('OLLAMA_PORT', '11434')
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
EXPORTER_PORT = int(os.environ.get('EXPORTER_PORT', '9200'))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', '15'))

# Metrics
ollama_up = Gauge('ollama_up', 'Whether Ollama API is accessible (1 = up, 0 = down)')
ollama_model_count = Gauge('ollama_model_count', 'Number of models available in Ollama')
ollama_model_size_bytes = Gauge('ollama_model_size_bytes', 'Size of model in bytes', ['model', 'family'])
ollama_api_response_time = Histogram('ollama_api_response_time_seconds', 'API response time in seconds', ['endpoint'])
ollama_api_errors_total = Counter('ollama_api_errors_total', 'Total number of API errors', ['endpoint'])

# Track inference metrics if available
ollama_inference_active = Gauge('ollama_inference_active', 'Whether inference is currently active (1 = yes, 0 = no)')
ollama_last_inference_timestamp = Gauge('ollama_last_inference_timestamp', 'Timestamp of last inference request')

class OllamaCollector:
    """Custom collector for Ollama metrics"""
    
    def __init__(self):
        self.last_inference_time = 0
        
    def collect(self):
        """Collect metrics from Ollama API"""
        try:
            # Check if Ollama is up by calling /api/tags
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
                
                # Track each model's size
                for model in models:
                    model_name = model.get('name', 'unknown')
                    model_size = model.get('size', 0)
                    model_family = model.get('details', {}).get('family', 'unknown')
                    
                    ollama_model_size_bytes.labels(
                        model=model_name,
                        family=model_family
                    ).set(model_size)
                    
                logger.info(f"Successfully collected metrics: {len(models)} models found")
                
            else:
                ollama_up.set(0)
                ollama_api_errors_total.labels(endpoint='tags').inc()
                logger.error(f"Ollama API returned status code: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            ollama_up.set(0)
            ollama_api_errors_total.labels(endpoint='tags').inc()
            logger.error(f"Failed to connect to Ollama API: {e}")
            
        except Exception as e:
            logger.error(f"Unexpected error collecting metrics: {e}")
            
        # Check for active inference (this is a heuristic since we don't have a status endpoint)
        try:
            # Try to get running models endpoint if it exists (future Ollama versions)
            response = requests.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=2)
            if response.status_code == 200:
                data = response.json()
                if data.get('models'):
                    ollama_inference_active.set(1)
                    self.last_inference_time = time.time()
                    ollama_last_inference_timestamp.set(self.last_inference_time)
                else:
                    ollama_inference_active.set(0)
        except:
            # If /api/ps doesn't exist, we can't determine inference status
            # Set to 0 if no recent activity (within last 60 seconds)
            if time.time() - self.last_inference_time > 60:
                ollama_inference_active.set(0)
        
        # Return empty list as we're using the global registry
        return []

def main():
    """Main function to start the exporter"""
    logger.info(f"Starting Ollama Prometheus Exporter on port {EXPORTER_PORT}")
    logger.info(f"Monitoring Ollama at {OLLAMA_BASE_URL}")
    
    # Register our custom collector
    collector = OllamaCollector()
    
    # Start HTTP server for Prometheus to scrape
    start_http_server(EXPORTER_PORT)
    logger.info(f"Exporter listening on port {EXPORTER_PORT}")
    
    # Main loop
    while True:
        try:
            # Collect metrics
            list(collector.collect())
            
        except KeyboardInterrupt:
            logger.info("Exporter stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            
        # Wait before next collection
        time.sleep(SCRAPE_INTERVAL)

if __name__ == "__main__":
    main()
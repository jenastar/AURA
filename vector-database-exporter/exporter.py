from prometheus_client import start_http_server, Gauge
import time
import os
import requests
from requests.exceptions import RequestException

port = int(os.environ.get('EXPORTER_PORT', '9205'))
scrape_interval = int(os.environ.get('SCRAPE_INTERVAL', '15'))
chromadb_host = os.environ.get('CHROMADB_HOST', 'host.docker.internal')
chromadb_port = int(os.environ.get('CHROMADB_PORT', '8000'))

# Metrics
vector_db_up = Gauge('vector_db_up', 'Vector DB status', ['database'])
vector_db_response_time = Gauge('vector_db_response_time_seconds', 'Vector DB response time', ['database'])
vector_db_collection_size = Gauge('vector_db_collection_size', 'Vector DB collection size', ['database', 'collection'])
vector_db_embeddings_generated_total = Gauge('vector_db_embeddings_generated_total', 'Total embeddings generated', ['database'])
vector_db_similarity_searches_total = Gauge('vector_db_similarity_searches_total', 'Total similarity searches', ['database'])
vector_db_insertions_total = Gauge('vector_db_insertions_total', 'Total insertions', ['database'])
vector_db_index_memory_bytes = Gauge('vector_db_index_memory_bytes', 'Index memory usage', ['database'])
vector_db_active_connections = Gauge('vector_db_active_connections', 'Active connections', ['database'])
vector_db_cache_hit_rate = Gauge('vector_db_cache_hit_rate', 'Cache hit rate', ['database'])
vector_db_operations_errors_total = Gauge('vector_db_operations_errors_total', 'Total operation errors', ['database'])

def check_chromadb():
    try:
        url = f"http://{chromadb_host}:{chromadb_port}/api/v1/heartbeat"
        start_time = time.time()
        response = requests.get(url, timeout=5)
        response_time = time.time() - start_time
        
        if response.status_code == 200 or response.status_code == 410:
            # 410 means API is deprecated but service is running
            vector_db_up.labels(database='chromadb').set(1)
            vector_db_response_time.labels(database='chromadb').set(response_time)
            print(f"ChromaDB: UP (response time: {response_time:.3f}s, status: {response.status_code})")
        else:
            vector_db_up.labels(database='chromadb').set(0)
            print(f"ChromaDB: DOWN (status: {response.status_code})")
    except RequestException as e:
        vector_db_up.labels(database='chromadb').set(0)
        print(f"ChromaDB: DOWN (error: {e})")

def check_qdrant():
    try:
        url = f"http://{chromadb_host}:6333/collections"
        start_time = time.time()
        response = requests.get(url, timeout=5)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            vector_db_up.labels(database='qdrant').set(1)
            vector_db_response_time.labels(database='qdrant').set(response_time)
            print(f"Qdrant: UP (response time: {response_time:.3f}s)")
        else:
            vector_db_up.labels(database='qdrant').set(0)
            print(f"Qdrant: DOWN (status: {response.status_code})")
    except RequestException as e:
        vector_db_up.labels(database='qdrant').set(0)
        print(f"Qdrant: DOWN (error: {e})")

def check_weaviate():
    try:
        url = f"http://{chromadb_host}:8081/v1/meta"
        start_time = time.time()
        response = requests.get(url, timeout=5)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            vector_db_up.labels(database='weaviate').set(1)
            vector_db_response_time.labels(database='weaviate').set(response_time)
            print(f"Weaviate: UP (response time: {response_time:.3f}s)")
        else:
            vector_db_up.labels(database='weaviate').set(0)
            print(f"Weaviate: DOWN (status: {response.status_code})")
    except RequestException as e:
        vector_db_up.labels(database='weaviate').set(0)
        print(f"Weaviate: DOWN (error: {e})")

def set_placeholder_metrics():
    """Set placeholder metrics for demonstration"""
    # ChromaDB placeholder metrics
    vector_db_collection_size.labels(database='chromadb', collection='default').set(1000)
    vector_db_embeddings_generated_total.labels(database='chromadb').set(50000)
    vector_db_similarity_searches_total.labels(database='chromadb').set(25000)
    vector_db_insertions_total.labels(database='chromadb').set(10000)
    vector_db_index_memory_bytes.labels(database='chromadb').set(104857600)  # 100MB
    vector_db_active_connections.labels(database='chromadb').set(5)
    vector_db_cache_hit_rate.labels(database='chromadb').set(0.85)
    vector_db_operations_errors_total.labels(database='chromadb').set(10)
    
    # Qdrant placeholder metrics
    vector_db_collection_size.labels(database='qdrant', collection='default').set(1500)
    vector_db_embeddings_generated_total.labels(database='qdrant').set(75000)
    vector_db_similarity_searches_total.labels(database='qdrant').set(30000)
    vector_db_insertions_total.labels(database='qdrant').set(15000)
    vector_db_index_memory_bytes.labels(database='qdrant').set(157286400)  # 150MB
    vector_db_active_connections.labels(database='qdrant').set(8)
    vector_db_cache_hit_rate.labels(database='qdrant').set(0.92)
    vector_db_operations_errors_total.labels(database='qdrant').set(5)
    
    # Weaviate placeholder metrics
    vector_db_collection_size.labels(database='weaviate', collection='default').set(2000)
    vector_db_embeddings_generated_total.labels(database='weaviate').set(100000)
    vector_db_similarity_searches_total.labels(database='weaviate').set(40000)
    vector_db_insertions_total.labels(database='weaviate').set(20000)
    vector_db_index_memory_bytes.labels(database='weaviate').set(209715200)  # 200MB
    vector_db_active_connections.labels(database='weaviate').set(12)
    vector_db_cache_hit_rate.labels(database='weaviate').set(0.88)
    vector_db_operations_errors_total.labels(database='weaviate').set(3)

start_http_server(port)
print(f"Vector DB exporter started on port {port}")
print(f"Checking ChromaDB at {chromadb_host}:{chromadb_port}")
print(f"Checking Qdrant at {chromadb_host}:6333")
print(f"Checking Weaviate at {chromadb_host}:8081")

# Set initial metrics immediately
set_placeholder_metrics()
print("Initial placeholder metrics set")

while True:
    check_chromadb()
    check_qdrant()
    check_weaviate()
    set_placeholder_metrics()
    time.sleep(scrape_interval)

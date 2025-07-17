#!/usr/bin/env python3
"""
Vector Database Metrics Exporter for Prometheus
Tracks embedding generation, similarity search, indexing, and storage metrics
for vector databases like ChromaDB, Pinecone, FAISS, Weaviate, etc.
"""

import os
import time
import json
import uuid
import threading
import statistics
import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from prometheus_client import (
    start_http_server, 
    Counter, 
    Gauge, 
    Histogram, 
    Summary,
    Info
)

# Vector Database Metrics
embeddings_generated_total = Counter(
    'vector_db_embeddings_generated_total',
    'Total number of embeddings generated',
    ['database', 'collection', 'model', 'dimension']
)

embedding_generation_time = Histogram(
    'vector_db_embedding_generation_seconds',
    'Time taken to generate embeddings',
    ['database', 'collection', 'model', 'batch_size'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float('inf'))
)

similarity_searches_total = Counter(
    'vector_db_similarity_searches_total',
    'Total number of similarity searches performed',
    ['database', 'collection', 'search_type']
)

similarity_search_latency = Histogram(
    'vector_db_similarity_search_seconds',
    'Time taken for similarity search',
    ['database', 'collection', 'search_type', 'top_k'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float('inf'))
)

vector_insertions_total = Counter(
    'vector_db_insertions_total',
    'Total number of vectors inserted',
    ['database', 'collection', 'batch_size']
)

vector_insertion_time = Histogram(
    'vector_db_insertion_seconds',
    'Time taken to insert vectors',
    ['database', 'collection', 'batch_size'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf'))
)

collection_size = Gauge(
    'vector_db_collection_size',
    'Number of vectors in collection',
    ['project', 'database', 'collection']
)

collection_dimension = Gauge(
    'vector_db_collection_dimension',
    'Dimension of vectors in collection',
    ['project', 'database', 'collection']
)

index_memory_usage_bytes = Gauge(
    'vector_db_index_memory_bytes',
    'Memory usage of vector index',
    ['database', 'collection', 'index_type']
)

similarity_scores = Histogram(
    'vector_db_similarity_scores',
    'Distribution of similarity scores',
    ['database', 'collection', 'search_type'],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0)
)

database_operations_errors = Counter(
    'vector_db_operations_errors_total',
    'Total number of database operation errors',
    ['database', 'collection', 'operation', 'error_type']
)

active_connections = Gauge(
    'vector_db_active_connections',
    'Number of active database connections',
    ['database', 'collection']
)

query_cache_hit_rate = Gauge(
    'vector_db_cache_hit_rate',
    'Cache hit rate for queries',
    ['database', 'collection']
)

index_build_time = Histogram(
    'vector_db_index_build_seconds',
    'Time taken to build or rebuild index',
    ['database', 'collection', 'index_type'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0, float('inf'))
)

database_info = Info(
    'vector_db_info',
    'Information about vector database instance',
    ['database', 'collection']
)


class VectorDatabaseMetricsTracker:
    """Base class for tracking vector database metrics"""
    
    def __init__(self, database_name: str):
        self.database_name = database_name
        self.active_operations: Dict[str, dict] = {}
        self.lock = threading.Lock()
        
    def start_operation(self, operation_id: str, operation_type: str, collection: str, **kwargs):
        """Start tracking an operation"""
        with self.lock:
            self.active_operations[operation_id] = {
                'start_time': time.time(),
                'operation_type': operation_type,
                'collection': collection,
                'metadata': kwargs
            }
    
    def end_operation(self, operation_id: str, success: bool = True, error_type: Optional[str] = None, **results):
        """End tracking an operation and update metrics"""
        with self.lock:
            if operation_id not in self.active_operations:
                return
                
            op = self.active_operations[operation_id]
            duration = time.time() - op['start_time']
            
            if not success and error_type:
                database_operations_errors.labels(
                    database=self.database_name,
                    collection=op['collection'],
                    operation=op['operation_type'],
                    error_type=error_type
                ).inc()
            
            # Update operation-specific metrics
            if op['operation_type'] == 'embedding_generation':
                if success:
                    batch_size = op['metadata'].get('batch_size', 1)
                    model = op['metadata'].get('model', 'unknown')
                    dimension = results.get('dimension', 0)
                    
                    embeddings_generated_total.labels(
                        database=self.database_name,
                        collection=op['collection'],
                        model=model,
                        dimension=str(dimension)
                    ).inc(batch_size)
                    
                    embedding_generation_time.labels(
                        database=self.database_name,
                        collection=op['collection'],
                        model=model,
                        batch_size=str(batch_size)
                    ).observe(duration)
            
            elif op['operation_type'] == 'similarity_search':
                if success:
                    search_type = op['metadata'].get('search_type', 'cosine')
                    top_k = op['metadata'].get('top_k', 10)
                    scores = results.get('similarity_scores', [])
                    
                    similarity_searches_total.labels(
                        database=self.database_name,
                        collection=op['collection'],
                        search_type=search_type
                    ).inc()
                    
                    similarity_search_latency.labels(
                        database=self.database_name,
                        collection=op['collection'],
                        search_type=search_type,
                        top_k=str(top_k)
                    ).observe(duration)
                    
                    # Track similarity score distribution
                    for score in scores:
                        similarity_scores.labels(
                            database=self.database_name,
                            collection=op['collection'],
                            search_type=search_type
                        ).observe(score)
            
            elif op['operation_type'] == 'vector_insertion':
                if success:
                    batch_size = op['metadata'].get('batch_size', 1)
                    
                    vector_insertions_total.labels(
                        database=self.database_name,
                        collection=op['collection'],
                        batch_size=str(batch_size)
                    ).inc(batch_size)
                    
                    vector_insertion_time.labels(
                        database=self.database_name,
                        collection=op['collection'],
                        batch_size=str(batch_size)
                    ).observe(duration)
            
            elif op['operation_type'] == 'index_build':
                if success:
                    index_type = op['metadata'].get('index_type', 'unknown')
                    
                    index_build_time.labels(
                        database=self.database_name,
                        collection=op['collection'],
                        index_type=index_type
                    ).observe(duration)
            
            del self.active_operations[operation_id]
    
    def update_collection_stats(self, collection: str, size: int, dimension: int):
        """Update collection size and dimension metrics"""
        collection_size.labels(
            project=self.project_label,
            database=self.database_name,
            collection=collection
        ).set(size)
        
        collection_dimension.labels(
            project=self.project_label,
            database=self.database_name,
            collection=collection
        ).set(dimension)
    
    def update_memory_usage(self, collection: str, index_type: str, memory_bytes: int):
        """Update index memory usage"""
        index_memory_usage_bytes.labels(
            database=self.database_name,
            collection=collection,
            index_type=index_type
        ).set(memory_bytes)
    
    def update_connections(self, collection: str, count: int):
        """Update active connection count"""
        active_connections.labels(
            database=self.database_name,
            collection=collection
        ).set(count)
    
    def update_cache_hit_rate(self, collection: str, hit_rate: float):
        """Update cache hit rate"""
        query_cache_hit_rate.labels(
            database=self.database_name,
            collection=collection
        ).set(hit_rate)


class ChromaDBMetricsCollector(VectorDatabaseMetricsTracker):
    """ChromaDB-specific metrics collector"""
    
    def __init__(self, chroma_client):
        super().__init__("chromadb")
        self.client = chroma_client
        
    def collect_metrics(self):
        """Collect metrics from ChromaDB"""
        try:
            # Get all collections
            collections = self.client.list_collections()
            
            for collection in collections:
                try:
                    # Get collection stats
                    count = collection.count()
                    self.update_collection_stats(collection.name, count, 0)  # ChromaDB doesn't expose dimension easily
                    
                    # Update database info
                    database_info.labels(
                        database=self.database_name,
                        collection=collection.name
                    ).info({
                        'type': 'chromadb',
                        'count': str(count),
                        'last_updated': datetime.now().isoformat()
                    })
                    
                except Exception as e:
                    database_operations_errors.labels(
                        database=self.database_name,
                        collection=collection.name,
                        operation='stats_collection',
                        error_type=type(e).__name__
                    ).inc()
                    
        except Exception as e:
            print(f"Error collecting ChromaDB metrics: {e}")


class PineconeMetricsCollector(VectorDatabaseMetricsTracker):
    """Pinecone-specific metrics collector"""
    
    def __init__(self, pinecone_index):
        super().__init__("pinecone")
        self.index = pinecone_index
        
    def collect_metrics(self):
        """Collect metrics from Pinecone"""
        try:
            # Get index stats
            stats = self.index.describe_index_stats()
            
            total_count = stats.get('total_vector_count', 0)
            dimension = stats.get('dimension', 0)
            
            self.update_collection_stats("default", total_count, dimension)
            
            # Update namespace stats if available
            namespaces = stats.get('namespaces', {})
            for namespace, ns_stats in namespaces.items():
                count = ns_stats.get('vector_count', 0)
                self.update_collection_stats(namespace, count, dimension)
                
                database_info.labels(
                    database=self.database_name,
                    collection=namespace
                ).info({
                    'type': 'pinecone',
                    'dimension': str(dimension),
                    'count': str(count),
                    'last_updated': datetime.now().isoformat()
                })
                
        except Exception as e:
            print(f"Error collecting Pinecone metrics: {e}")


class FAISSMetricsCollector(VectorDatabaseMetricsTracker):
    """FAISS-specific metrics collector"""
    
    def __init__(self, faiss_indices: Dict[str, Any]):
        super().__init__("faiss")
        self.indices = faiss_indices  # Dict of collection_name -> faiss_index
        
    def collect_metrics(self):
        """Collect metrics from FAISS indices"""
        try:
            for collection_name, index in self.indices.items():
                try:
                    # Get index stats
                    count = index.ntotal
                    dimension = index.d
                    
                    self.update_collection_stats(collection_name, count, dimension)
                    
                    # Estimate memory usage (rough approximation)
                    memory_bytes = count * dimension * 4  # Assuming float32
                    self.update_memory_usage(collection_name, "faiss", memory_bytes)
                    
                    database_info.labels(
                        database=self.database_name,
                        collection=collection_name
                    ).info({
                        'type': 'faiss',
                        'dimension': str(dimension),
                        'count': str(count),
                        'is_trained': str(index.is_trained),
                        'last_updated': datetime.now().isoformat()
                    })
                    
                except Exception as e:
                    database_operations_errors.labels(
                        database=self.database_name,
                        collection=collection_name,
                        operation='stats_collection',
                        error_type=type(e).__name__
                    ).inc()
                    
        except Exception as e:
            print(f"Error collecting FAISS metrics: {e}")


class VectorDatabaseWrapper:
    """Generic wrapper for vector database operations with metrics"""
    
    def __init__(self, database_type: str, database_instance, metrics_tracker: VectorDatabaseMetricsTracker):
        self.database_type = database_type
        self.database = database_instance
        self.tracker = metrics_tracker
    
    def embed_documents(self, documents: List[str], collection: str, model: str = "default", **kwargs):
        """Wrap document embedding with metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id, 
                'embedding_generation', 
                collection,
                batch_size=len(documents),
                model=model
            )
            
            # Call the actual embedding function
            # This would be customized based on your actual implementation
            embeddings = self._generate_embeddings(documents, model, **kwargs)
            
            self.tracker.end_operation(
                operation_id, 
                success=True,
                dimension=len(embeddings[0]) if embeddings else 0
            )
            
            return embeddings
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id, 
                success=False, 
                error_type=type(e).__name__
            )
            raise
    
    def similarity_search(self, query_vector: List[float], collection: str, top_k: int = 10, search_type: str = "cosine", **kwargs):
        """Wrap similarity search with metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'similarity_search',
                collection,
                top_k=top_k,
                search_type=search_type
            )
            
            # Call the actual search function
            results = self._perform_search(query_vector, collection, top_k, search_type, **kwargs)
            
            # Extract similarity scores from results
            scores = [result.get('score', 0) for result in results]
            
            self.tracker.end_operation(
                operation_id,
                success=True,
                similarity_scores=scores
            )
            
            return results
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id,
                success=False,
                error_type=type(e).__name__
            )
            raise
    
    def insert_vectors(self, vectors: List[List[float]], collection: str, metadata: Optional[List[dict]] = None, **kwargs):
        """Wrap vector insertion with metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'vector_insertion',
                collection,
                batch_size=len(vectors)
            )
            
            # Call the actual insertion function
            result = self._insert_vectors(vectors, collection, metadata, **kwargs)
            
            self.tracker.end_operation(operation_id, success=True)
            return result
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id,
                success=False,
                error_type=type(e).__name__
            )
            raise
    
    def build_index(self, collection: str, index_type: str = "default", **kwargs):
        """Wrap index building with metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'index_build',
                collection,
                index_type=index_type
            )
            
            # Call the actual index building function
            result = self._build_index(collection, index_type, **kwargs)
            
            self.tracker.end_operation(operation_id, success=True)
            return result
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id,
                success=False,
                error_type=type(e).__name__
            )
            raise
    
    # These methods would be implemented based on the specific database
    def _generate_embeddings(self, documents, model, **kwargs):
        raise NotImplementedError("Implement for specific database")
    
    def _perform_search(self, query_vector, collection, top_k, search_type, **kwargs):
        raise NotImplementedError("Implement for specific database")
    
    def _insert_vectors(self, vectors, collection, metadata, **kwargs):
        raise NotImplementedError("Implement for specific database")
    
    def _build_index(self, collection, index_type, **kwargs):
        raise NotImplementedError("Implement for specific database")


def create_demo_data():
    """Create demo metrics for testing"""
    import random
    
    # Create dummy tracker
    tracker = VectorDatabaseMetricsTracker("demo")
    tracker.project_label = os.environ.get('PROJECT_LABEL', 'mon')
    
    # Simulate some operations
    collections = ["documents", "images", "audio"]
    models = ["sentence-transformers", "openai-ada", "custom-bert"]
    
    for _ in range(100):  # Simulate 100 operations
        collection = random.choice(collections)
        model = random.choice(models)
        
        # Simulate embedding generation
        op_id = str(uuid.uuid4())
        tracker.start_operation(op_id, 'embedding_generation', collection, 
                              batch_size=random.randint(1, 50), model=model)
        time.sleep(random.uniform(0.001, 0.1))  # Simulate processing time
        tracker.end_operation(op_id, success=True, dimension=768)
        
        # Simulate similarity search
        op_id = str(uuid.uuid4())
        tracker.start_operation(op_id, 'similarity_search', collection, 
                              top_k=random.randint(5, 20), search_type='cosine')
        time.sleep(random.uniform(0.001, 0.05))
        scores = [random.uniform(0.7, 0.99) for _ in range(random.randint(5, 20))]
        tracker.end_operation(op_id, success=True, similarity_scores=scores)
        
        # Simulate vector insertion
        op_id = str(uuid.uuid4())
        batch_size = random.randint(10, 100)
        tracker.start_operation(op_id, 'vector_insertion', collection, 
                              batch_size=batch_size)
        time.sleep(random.uniform(0.01, 0.2))  # Insertions take longer
        tracker.end_operation(op_id, success=True)
        
        # Update collection stats
        tracker.update_collection_stats(collection, random.randint(1000, 100000), 768)
        
        # Update memory usage
        tracker.update_memory_usage(collection, "hnsw", random.randint(100000000, 1000000000))
        
        # Update connections
        tracker.update_connections(collection, random.randint(1, 10))
        
        # Update cache hit rate
        tracker.update_cache_hit_rate(collection, random.uniform(0.6, 0.95))
        
        # Occasionally simulate index building (less frequent)
        if random.random() < 0.05:  # 5% chance
            op_id = str(uuid.uuid4())
            index_type = random.choice(["hnsw", "ivf", "flat"])
            tracker.start_operation(op_id, 'index_build', collection, 
                                  index_type=index_type)
            time.sleep(random.uniform(1.0, 5.0))  # Index building takes much longer
            tracker.end_operation(op_id, success=True)


def main():
    # Configuration
    port = int(os.environ.get('EXPORTER_PORT', '9205'))
    scrape_interval = int(os.environ.get('SCRAPE_INTERVAL', '15'))
    demo_mode = os.environ.get('DEMO_MODE', 'true').lower() == 'true'
    
    # Start Prometheus metrics server
    start_http_server(port)
    print(f"Vector Database Metrics Exporter started on port {port}")
    
    if demo_mode:
        print("Running in demo mode - generating sample metrics")
        
        # Generate initial demo data
        create_demo_data()
        print("Initial demo data generated")
        
        # Keep server running and periodically generate more data
        while True:
            time.sleep(scrape_interval)
            # Generate a few more operations each cycle
            tracker = VectorDatabaseMetricsTracker("demo")
            tracker.project_label = os.environ.get('PROJECT_LABEL', 'mon')
            collections = ["documents", "images", "audio"]
            
            for _ in range(5):  # Generate 5 operations per cycle
                collection = random.choice(collections)
                
                # Add some vector insertions
                op_id = str(uuid.uuid4())
                batch_size = random.randint(10, 100)
                tracker.start_operation(op_id, 'vector_insertion', collection, 
                                      batch_size=batch_size)
                time.sleep(random.uniform(0.01, 0.1))
                tracker.end_operation(op_id, success=True)
    else:
        print("Production mode - connect to actual vector databases")
        # Initialize actual database collectors
        collectors = []
        
        if 'CHROMADB_HOST' in os.environ:
            try:
                import chromadb
                host = os.environ.get('CHROMADB_HOST', 'localhost')
                port_num = int(os.environ.get('CHROMADB_PORT', '8000'))
                print(f"Connecting to ChromaDB at {host}:{port_num}")
                client = chromadb.HttpClient(host=host, port=port_num)
                project_label = os.environ.get('PROJECT_LABEL', 'mon')
                collector = ChromaDBMetricsCollector(client)
                collector.project_label = project_label
                collectors.append(collector)
                print("ChromaDB collector initialized")
            except Exception as e:
                print(f"Failed to initialize ChromaDB collector: {e}")
                import traceback
                traceback.print_exc()
        
        if not collectors:
            print("No collectors initialized, running in passive mode")
        
        while True:
            for collector in collectors:
                try:
                    collector.collect_metrics()
                except Exception as e:
                    print(f"Error collecting metrics: {e}")
            time.sleep(scrape_interval)


if __name__ == "__main__":
    main()
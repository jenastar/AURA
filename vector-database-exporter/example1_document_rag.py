#!/usr/bin/env python3
"""
Example 1: Document Knowledge Base RAG System
Monitors document indexing and retrieval for a technical documentation system
"""

import chromadb
from chromadb.utils import embedding_functions
import time
import sys
sys.path.append('/app')  # For Docker
try:
    from chromadb_wrapper import ChromaDBWrapper
except:
    # If running locally, adjust path
    sys.path.append('.')
    from chromadb_wrapper import ChromaDBWrapper

# Technical documentation samples
TECHNICAL_DOCS = [
    {
        "id": "docker-001",
        "content": "Docker containers package applications with their dependencies, ensuring consistency across different environments. Use 'docker run' to start containers and 'docker build' to create images from Dockerfiles.",
        "metadata": {"category": "docker", "type": "basics", "difficulty": "beginner"}
    },
    {
        "id": "k8s-001",
        "content": "Kubernetes orchestrates containerized applications across clusters. Pods are the smallest deployable units, while Services provide network access to pods. Deployments manage the desired state of your applications.",
        "metadata": {"category": "kubernetes", "type": "concepts", "difficulty": "intermediate"}
    },
    {
        "id": "prometheus-001",
        "content": "Prometheus scrapes metrics from configured targets using a pull model. Metrics are stored in a time-series database and can be queried using PromQL. Use recording rules to precompute frequently needed expressions.",
        "metadata": {"category": "monitoring", "type": "metrics", "difficulty": "intermediate"}
    },
    {
        "id": "grafana-001",
        "content": "Grafana visualizes metrics from various data sources including Prometheus. Create dashboards with panels showing graphs, gauges, and tables. Use variables to make dashboards dynamic and reusable.",
        "metadata": {"category": "monitoring", "type": "visualization", "difficulty": "beginner"}
    },
    {
        "id": "python-001",
        "content": "Python decorators modify function behavior without changing the function code. Use @property for getters/setters, @staticmethod for methods that don't need self, and @classmethod for factory methods.",
        "metadata": {"category": "programming", "type": "python", "difficulty": "intermediate"}
    }
]

def run_document_rag_example():
    """Demonstrates document indexing and retrieval with monitoring"""
    
    print("=" * 60)
    print("Example 1: Document Knowledge Base RAG System")
    print("=" * 60)
    
    # Initialize ChromaDB with monitoring
    client = chromadb.HttpClient(host="localhost", port=8000)
    
    # Use sentence transformers for better embeddings
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    # Create monitored wrapper
    db = ChromaDBWrapper(client, embedding_fn)
    
    # 1. Create collection for technical docs
    collection_name = "technical_documentation"
    print(f"\n1. Creating collection: {collection_name}")
    
    try:
        client.delete_collection(collection_name)
    except:
        pass
    
    db.create_collection(
        name=collection_name,
        metadata={"description": "Technical documentation knowledge base"}
    )
    
    # 2. Index documents (generates embedding and insertion metrics)
    print("\n2. Indexing technical documentation...")
    start_time = time.time()
    
    result = db.add_documents(
        collection_name=collection_name,
        documents=[doc["content"] for doc in TECHNICAL_DOCS],
        metadata=[doc["metadata"] for doc in TECHNICAL_DOCS],
        ids=[doc["id"] for doc in TECHNICAL_DOCS]
    )
    
    indexing_time = time.time() - start_time
    print(f"   Indexed {len(TECHNICAL_DOCS)} documents in {indexing_time:.2f} seconds")
    print(f"   Result: {result}")
    
    # 3. Perform various searches (generates search metrics)
    queries = [
        "How do I create a Docker container?",
        "What is Kubernetes used for?",
        "How to visualize Prometheus metrics?",
        "Explain Python decorators",
        "What is the difference between Docker and Kubernetes?"
    ]
    
    print("\n3. Performing searches...")
    for i, query in enumerate(queries, 1):
        print(f"\n   Query {i}: {query}")
        
        start_time = time.time()
        results = db.search_documents(
            collection_name=collection_name,
            query=query,
            top_k=3
        )
        search_time = time.time() - start_time
        
        print(f"   Search completed in {search_time:.3f} seconds")
        print(f"   Top result: {results[0]['document'][:80]}...")
        print(f"   Similarity score: {results[0]['score']:.3f}")
    
    # 4. Get collection statistics
    print("\n4. Collection Statistics:")
    stats = db.get_collection_stats(collection_name)
    print(f"   {stats}")
    
    print("\n✅ Example 1 complete! Check Grafana for metrics.")
    print("   - Embedding generation time")
    print("   - Vector insertion count and latency")
    print("   - Search performance and similarity scores")
    
    return db, collection_name


if __name__ == "__main__":
    run_document_rag_example()
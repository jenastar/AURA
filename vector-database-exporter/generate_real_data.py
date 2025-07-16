#!/usr/bin/env python3
"""
Generate real vector database metrics using direct HTTP API calls
"""

import requests
import json
import time
import random
import hashlib

CHROMADB_HOST = "http://localhost:8000"

def generate_embedding(text, dimension=384):
    """Generate a deterministic embedding from text"""
    # Use hash to create consistent embeddings
    hash_obj = hashlib.sha256(text.encode())
    hash_bytes = hash_obj.digest()
    
    # Convert to floats between -1 and 1
    embedding = []
    for i in range(0, dimension):
        byte_idx = i % len(hash_bytes)
        value = (hash_bytes[byte_idx] / 127.5) - 1.0
        embedding.append(value)
    
    return embedding

def main():
    print("Generating real vector database activity...")
    
    # Test ChromaDB connection
    try:
        response = requests.get(f"{CHROMADB_HOST}/api/v1/heartbeat")
        print(f"ChromaDB heartbeat: {response.json()}")
    except Exception as e:
        print(f"Error connecting to ChromaDB: {e}")
        return
    
    # Create a test collection
    collection_name = f"rag_test_{int(time.time())}"
    print(f"\nCreating collection: {collection_name}")
    
    # Create collection
    response = requests.post(
        f"{CHROMADB_HOST}/api/v1/collections",
        json={
            "name": collection_name,
            "metadata": {"hnsw:space": "cosine"}
        }
    )
    print(f"Collection creation response: {response.status_code}")
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return
    
    collection_id = response.json()["id"]
    print(f"Collection ID: {collection_id}")
    
    # Generate and add documents
    print("\nAdding documents...")
    
    # Technical documentation samples
    documents = [
        "Docker containers provide lightweight virtualization for applications",
        "Kubernetes orchestrates containers across multiple nodes in a cluster",
        "Prometheus collects metrics using a pull-based monitoring approach",
        "Grafana visualizes time-series data from multiple data sources",
        "Python is a versatile language for data science and web development",
        "Go is designed for building scalable networked services",
        "Rust provides memory safety without garbage collection",
        "Vector databases store high-dimensional embeddings for similarity search",
        "LLMs use transformer architectures for natural language understanding",
        "RAG systems combine retrieval with generation for better responses"
    ]
    
    # Add documents in batches
    batch_size = 5
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i+batch_size]
        batch_ids = [f"doc_{j}" for j in range(i, i+batch_size)]
        batch_embeddings = [generate_embedding(doc) for doc in batch_docs]
        batch_metadata = [{"index": j, "category": "technical"} for j in range(i, i+batch_size)]
        
        add_response = requests.post(
            f"{CHROMADB_HOST}/api/v1/collections/{collection_id}/add",
            json={
                "ids": batch_ids,
                "documents": batch_docs,
                "embeddings": batch_embeddings,
                "metadatas": batch_metadata
            }
        )
        print(f"  Added batch {i//batch_size + 1}: {add_response.status_code}")
        time.sleep(0.5)
    
    # Perform similarity searches
    print("\nPerforming searches...")
    
    queries = [
        "How to deploy containers?",
        "Monitoring and observability tools",
        "Programming language for systems",
        "Machine learning and AI",
        "Database for embeddings"
    ]
    
    for query in queries:
        query_embedding = generate_embedding(query)
        
        search_response = requests.post(
            f"{CHROMADB_HOST}/api/v1/collections/{collection_id}/query",
            json={
                "query_embeddings": [query_embedding],
                "n_results": 3
            }
        )
        
        if search_response.status_code == 200:
            results = search_response.json()
            print(f"\n  Query: '{query}'")
            if results["documents"] and len(results["documents"][0]) > 0:
                print(f"  Top result: '{results['documents'][0][0][:60]}...'")
                print(f"  Distance: {results['distances'][0][0]:.3f}")
        else:
            print(f"  Search error: {search_response.status_code}")
        
        time.sleep(0.3)
    
    # Check collection info
    print("\nChecking collection stats...")
    count_response = requests.get(f"{CHROMADB_HOST}/api/v1/collections/{collection_id}/count")
    if count_response.status_code == 200:
        print(f"  Document count: {count_response.json()}")
    
    # Check metrics
    print("\nChecking metrics endpoint...")
    try:
        metrics_response = requests.get("http://localhost:9205/metrics")
        if metrics_response.status_code == 200:
            lines = metrics_response.text.split('\n')
            vector_metrics = [l for l in lines if 'vector_db' in l and not l.startswith('#')]
            print(f"  Found {len(vector_metrics)} vector database metrics")
            # Show some key metrics
            for metric in vector_metrics:
                if any(key in metric for key in ['embeddings_generated', 'insertions_total', 'similarity_searches']):
                    print(f"    {metric}")
    except Exception as e:
        print(f"  Error checking metrics: {e}")
    
    print("\n✅ Real data generation complete!")
    print("Check Grafana dashboard at http://localhost:3000")

if __name__ == "__main__":
    main()
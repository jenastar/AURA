#!/usr/bin/env python3
"""
Simple RAG test that generates real vector database metrics
"""

import requests
import json
import time
import random

# ChromaDB API endpoints
CHROMADB_HOST = "http://localhost:8000"
METRICS_HOST = "http://localhost:9205"

def create_collection(name="test_documents"):
    """Create a collection in ChromaDB"""
    print(f"Creating collection: {name}")
    
    # Delete if exists
    requests.delete(f"{CHROMADB_HOST}/api/v1/collections/{name}")
    
    # Create new collection
    response = requests.post(
        f"{CHROMADB_HOST}/api/v1/collections",
        json={
            "name": name,
            "metadata": {"description": "Test document collection"}
        }
    )
    print(f"Collection created: {response.status_code}")
    return name

def add_documents(collection_name, num_docs=50):
    """Add documents to collection"""
    print(f"\nAdding {num_docs} documents...")
    
    documents = []
    embeddings = []
    metadata = []
    ids = []
    
    # Generate test documents
    topics = ["kubernetes", "docker", "prometheus", "grafana", "python", "golang", "rust", "javascript"]
    for i in range(num_docs):
        topic = random.choice(topics)
        doc = f"Document {i}: This is a technical document about {topic}. It covers best practices for {topic} implementation."
        
        documents.append(doc)
        # Generate random embedding (384 dimensions for all-MiniLM-L6-v2)
        embeddings.append([random.random() for _ in range(384)])
        metadata.append({"topic": topic, "doc_id": i})
        ids.append(f"doc_{i:04d}")
    
    # Add in batches
    batch_size = 10
    for i in range(0, num_docs, batch_size):
        batch_end = min(i + batch_size, num_docs)
        
        response = requests.post(
            f"{CHROMADB_HOST}/api/v1/collections/{collection_name}/add",
            json={
                "documents": documents[i:batch_end],
                "embeddings": embeddings[i:batch_end],
                "metadatas": metadata[i:batch_end],
                "ids": ids[i:batch_end]
            }
        )
        print(f"  Added batch {i//batch_size + 1}: {response.status_code}")
        time.sleep(0.5)  # Small delay between batches

def search_documents(collection_name, num_searches=20):
    """Perform searches on the collection"""
    print(f"\nPerforming {num_searches} searches...")
    
    queries = [
        "How to implement kubernetes pods?",
        "Docker container best practices",
        "Prometheus monitoring setup",
        "Grafana dashboard configuration",
        "Python performance optimization",
        "Golang concurrency patterns",
        "Rust memory safety",
        "JavaScript async programming"
    ]
    
    for i in range(num_searches):
        query = random.choice(queries)
        # Generate random query embedding
        query_embedding = [random.random() for _ in range(384)]
        
        response = requests.post(
            f"{CHROMADB_HOST}/api/v1/collections/{collection_name}/query",
            json={
                "query_embeddings": [query_embedding],
                "n_results": 5
            }
        )
        
        if response.status_code == 200:
            results = response.json()
            print(f"  Search {i+1}: Found {len(results['documents'][0])} results")
        else:
            print(f"  Search {i+1}: Error {response.status_code}")
        
        time.sleep(0.2)  # Small delay between searches

def check_metrics():
    """Check if metrics are being generated"""
    print("\nChecking metrics endpoint...")
    try:
        response = requests.get(f"{METRICS_HOST}/metrics")
        if response.status_code == 200:
            metrics = response.text
            vector_metrics = [line for line in metrics.split('\n') if 'vector_db' in line and not line.startswith('#')]
            print(f"Found {len(vector_metrics)} vector database metrics")
            for metric in vector_metrics[:10]:  # Show first 10
                print(f"  {metric}")
        else:
            print(f"Metrics endpoint returned: {response.status_code}")
    except Exception as e:
        print(f"Error checking metrics: {e}")

def main():
    print("=" * 60)
    print("Simple RAG Test - Generating Real Vector DB Metrics")
    print("=" * 60)
    
    # Create collection
    collection_name = create_collection()
    
    # Add documents
    add_documents(collection_name, num_docs=50)
    
    # Perform searches
    search_documents(collection_name, num_searches=20)
    
    # Check metrics
    check_metrics()
    
    print("\n✅ Test complete! Check Grafana for real metrics.")

if __name__ == "__main__":
    main()
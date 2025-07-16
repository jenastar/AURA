#!/usr/bin/env python3
"""
Generate real vector database metrics by creating a ChromaDB client
that will be tracked by the vector exporter
"""

import os
import sys
import time
import random

# Add the exporter path to import the wrapper
sys.path.append('/mnt/c/dev/aura/vector-database-exporter')

try:
    from chromadb_wrapper import ChromaDBWrapper
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:
    print("Installing required packages...")
    os.system("pip install chromadb==0.4.15 sentence-transformers==2.2.2")
    from chromadb_wrapper import ChromaDBWrapper
    import chromadb
    from chromadb.utils import embedding_functions

def main():
    print("Generating real vector database metrics...")
    
    # Connect to ChromaDB
    print("Connecting to ChromaDB...")
    client = chromadb.HttpClient(host="localhost", port=8000)
    
    # Create embedding function
    embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    
    # Create wrapped client for metrics tracking
    db = ChromaDBWrapper(client, embedding_fn)
    
    # Create a test collection
    collection_name = f"real_test_{int(time.time())}"
    print(f"\nCreating collection: {collection_name}")
    
    try:
        db.create_collection(
            name=collection_name,
            metadata={"description": "Real test collection for metrics"}
        )
    except Exception as e:
        print(f"Error creating collection: {e}")
        # Try to use existing collection
        collections = client.list_collections()
        if collections:
            collection_name = collections[0].name
            print(f"Using existing collection: {collection_name}")
        else:
            return
    
    # Generate some real documents
    documents = [
        "Docker provides containerization for applications",
        "Kubernetes orchestrates containers at scale",
        "Prometheus monitors system metrics",
        "Grafana visualizes time-series data",
        "Vector databases enable similarity search",
        "Machine learning models generate embeddings",
        "RAG systems combine retrieval and generation",
        "LLMs process natural language efficiently",
        "Monitoring helps maintain system health",
        "Observability provides system insights"
    ]
    
    # Add documents
    print("\nAdding documents...")
    try:
        result = db.add_documents(
            collection_name=collection_name,
            documents=documents,
            metadata=[{"index": i} for i in range(len(documents))],
            ids=[f"doc_{i}" for i in range(len(documents))]
        )
        print(f"Added {len(documents)} documents")
    except Exception as e:
        print(f"Error adding documents: {e}")
    
    # Perform searches
    print("\nPerforming searches...")
    queries = [
        "container orchestration",
        "monitoring and observability",
        "vector similarity search",
        "machine learning embeddings",
        "system metrics visualization"
    ]
    
    for query in queries:
        try:
            results = db.search_documents(
                collection_name=collection_name,
                query=query,
                top_k=3
            )
            print(f"Query '{query}': Found {len(results)} results")
        except Exception as e:
            print(f"Error searching: {e}")
        time.sleep(0.5)
    
    # Get collection stats
    try:
        stats = db.get_collection_stats(collection_name)
        print(f"\nCollection stats: {stats}")
    except Exception as e:
        print(f"Error getting stats: {e}")
    
    print("\n✅ Real metrics generation complete!")
    print("Check http://localhost:9205/metrics for vector_db metrics")
    print("Check Grafana at http://localhost:3000")

if __name__ == "__main__":
    main()
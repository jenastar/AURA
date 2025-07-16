#!/usr/bin/env python3
"""
Test application to generate real vector database operations
"""
import chromadb
import time
import random
import numpy as np
from datetime import datetime

def generate_random_embedding(dimension=384):
    """Generate a random embedding vector"""
    embedding = np.random.randn(dimension)
    # Normalize to unit vector
    embedding = embedding / np.linalg.norm(embedding)
    return embedding.tolist()

def main():
    # Connect to ChromaDB
    import os
    chromadb_host = os.environ.get('CHROMADB_HOST', 'chromadb')
    chromadb_port = int(os.environ.get('CHROMADB_PORT', '8000'))
    client = chromadb.HttpClient(host=chromadb_host, port=chromadb_port)
    print(f"Connecting to ChromaDB at {chromadb_host}:{chromadb_port}")
    
    # Create or get test collection
    collection_name = "test_rag_documents"
    try:
        collection = client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"Created collection: {collection_name}")
    except:
        collection = client.get_collection(collection_name)
        print(f"Using existing collection: {collection_name}")
    
    # Test documents
    documents = [
        "The quick brown fox jumps over the lazy dog",
        "Machine learning is transforming how we process information",
        "Vector databases enable semantic search capabilities",
        "RAG combines retrieval with generation for better AI responses",
        "ChromaDB is a vector database designed for AI applications",
        "Embeddings capture semantic meaning in high-dimensional space",
        "Similarity search finds related documents based on meaning",
        "LLMs benefit from access to external knowledge bases",
        "Vector search is more powerful than keyword search",
        "Monitoring helps optimize vector database performance"
    ]
    
    print(f"\nStarting continuous vector operations at {datetime.now()}")
    operation_count = 0
    
    while True:
        try:
            # Insert documents with embeddings
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Inserting batch of documents...")
            batch_size = random.randint(1, 5)
            batch_docs = random.sample(documents, batch_size)
            batch_embeddings = [generate_random_embedding() for _ in range(batch_size)]
            batch_ids = [f"doc_{operation_count}_{i}" for i in range(batch_size)]
            
            collection.add(
                documents=batch_docs,
                embeddings=batch_embeddings,
                ids=batch_ids,
                metadatas=[{"timestamp": datetime.now().isoformat()} for _ in range(batch_size)]
            )
            print(f"✓ Inserted {batch_size} documents")
            operation_count += batch_size
            
            # Perform similarity search
            time.sleep(1)
            query_text = random.choice(documents)
            query_embedding = generate_random_embedding()
            n_results = random.randint(3, 10)
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Searching for: '{query_text[:50]}...'")
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            print(f"✓ Found {len(results['ids'][0])} similar documents")
            
            # Show collection stats
            count = collection.count()
            print(f"\n📊 Collection stats: {count} total documents")
            
            # Random delay between operations
            delay = random.uniform(2, 5)
            print(f"\n💤 Waiting {delay:.1f} seconds before next operation...")
            time.sleep(delay)
            
        except KeyboardInterrupt:
            print("\n\nStopping test application...")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            time.sleep(5)
    
    print(f"\nTest completed. Total operations: {operation_count}")

if __name__ == "__main__":
    main()
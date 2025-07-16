#!/usr/bin/env python3
"""
Example: How to use Vector Database Monitoring in Your Application

This shows how to integrate the monitoring wrappers into your existing code
"""

import chromadb
from chromadb.utils import embedding_functions
from chromadb_wrapper import ChromaDBWrapper

# Example 1: Basic ChromaDB Usage with Monitoring
def example_basic_usage():
    """Basic example of using ChromaDB with automatic monitoring"""
    
    # 1. Initialize ChromaDB client (same as usual)
    client = chromadb.HttpClient(host="localhost", port=8000)
    
    # 2. Create the monitoring wrapper
    db = ChromaDBWrapper(client)
    
    # 3. Create a collection (metrics are automatically tracked)
    collection_name = "my_documents"
    db.create_collection(collection_name)
    
    # 4. Add documents (insertion metrics are tracked)
    documents = [
        "The quick brown fox jumps over the lazy dog",
        "Machine learning is transforming how we process information",
        "Vector databases enable semantic search at scale"
    ]
    
    db.add_documents(
        collection_name=collection_name,
        documents=documents,
        metadata=[
            {"source": "example", "type": "test"},
            {"source": "ml", "type": "info"},
            {"source": "db", "type": "tech"}
        ]
    )
    
    # 5. Search documents (search metrics are tracked)
    results = db.search_documents(
        collection_name=collection_name,
        query="What is machine learning?",
        top_k=2
    )
    
    print("Search results:")
    for result in results:
        print(f"- {result['document'][:50]}... (score: {result['score']:.3f})")
    
    # All operations above automatically generate metrics!


# Example 2: Advanced RAG Pipeline with Monitoring
class MonitoredRAGPipeline:
    """Example RAG pipeline with built-in monitoring"""
    
    def __init__(self, chroma_host="localhost", chroma_port=8000):
        # Initialize ChromaDB with monitoring
        self.client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        self.db = ChromaDBWrapper(self.client)
        
        # Use a specific embedding model
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        self.collection_name = "knowledge_base"
        
    def initialize_knowledge_base(self, documents):
        """Initialize the knowledge base with documents"""
        
        # Create collection with custom embedding function
        self.db.create_collection(
            name=self.collection_name,
            metadata={"description": "RAG knowledge base"},
            embedding_function=self.embedding_function
        )
        
        # Batch insert documents
        # Metrics tracked: vector_db_insertions_total, vector_db_insertion_seconds
        result = self.db.add_documents(
            collection_name=self.collection_name,
            documents=[doc["content"] for doc in documents],
            metadata=[doc["metadata"] for doc in documents],
            ids=[doc["id"] for doc in documents]
        )
        
        print(f"Initialized knowledge base with {len(documents)} documents")
        return result
    
    def answer_question(self, question, context_limit=3):
        """Answer a question using RAG"""
        
        # 1. Search for relevant context
        # Metrics tracked: vector_db_similarity_searches_total, 
        #                  vector_db_similarity_search_seconds,
        #                  vector_db_similarity_scores
        search_results = self.db.search_documents(
            collection_name=self.collection_name,
            query=question,
            top_k=context_limit
        )
        
        # 2. Build context from search results
        context = "\n\n".join([
            f"Context {i+1}: {result['document']}"
            for i, result in enumerate(search_results)
        ])
        
        # 3. Generate answer (this is where you'd call your LLM)
        answer = self._generate_answer(question, context)
        
        return {
            "question": question,
            "answer": answer,
            "sources": search_results,
            "context_used": len(search_results)
        }
    
    def _generate_answer(self, question, context):
        """Placeholder for LLM answer generation"""
        # In a real implementation, this would call your LLM
        # For example: openai.ChatCompletion.create(...)
        return f"Based on the context, here's an answer to '{question}': [LLM response would go here]"


# Example 3: Monitoring Custom Operations
def example_custom_metrics():
    """Example of tracking custom vector database operations"""
    
    from vector_db_metrics_exporter import VectorDatabaseMetricsTracker
    import uuid
    import time
    
    # Create a metrics tracker for custom operations
    tracker = VectorDatabaseMetricsTracker("my_custom_db")
    
    # Track a custom embedding generation operation
    operation_id = str(uuid.uuid4())
    tracker.start_operation(
        operation_id=operation_id,
        operation_type='embedding_generation',
        collection='custom_collection',
        batch_size=100,
        model='custom-bert'
    )
    
    # Simulate some work
    time.sleep(0.1)
    
    # Complete the operation
    tracker.end_operation(
        operation_id=operation_id,
        success=True,
        dimension=768
    )
    
    # Update collection statistics
    tracker.update_collection_stats(
        collection='custom_collection',
        size=10000,
        dimension=768
    )
    
    # Track memory usage
    tracker.update_memory_usage(
        collection='custom_collection',
        index_type='hnsw',
        memory_bytes=1024 * 1024 * 100  # 100MB
    )


# Example 4: Production Configuration
def example_production_setup():
    """Example of production setup with error handling and monitoring"""
    
    import os
    import logging
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Get configuration from environment
    chroma_host = os.environ.get('CHROMADB_HOST', 'localhost')
    chroma_port = int(os.environ.get('CHROMADB_PORT', '8000'))
    
    try:
        # Initialize client with monitoring
        client = chromadb.HttpClient(
            host=chroma_host,
            port=chroma_port,
            timeout=30
        )
        
        # Create wrapper
        db = ChromaDBWrapper(client)
        
        # Test connection
        collections = client.list_collections()
        logger.info(f"Connected to ChromaDB. Found {len(collections)} collections")
        
        # Your application logic here
        # All database operations through 'db' will be monitored
        
        return db
        
    except Exception as e:
        logger.error(f"Failed to connect to ChromaDB: {e}")
        logger.info("Metrics will show connection errors")
        raise


if __name__ == "__main__":
    print("Vector Database Monitoring Examples")
    print("===================================\n")
    
    print("1. Basic Usage Example:")
    try:
        example_basic_usage()
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n2. Custom Metrics Example:")
    example_custom_metrics()
    
    print("\n3. Production Setup Example:")
    try:
        db = example_production_setup()
        print("   Successfully configured for production")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\nCheck http://localhost:9205/metrics to see the generated metrics!")
    print("View in Grafana at http://localhost:3000 - Vector Database Monitoring dashboard")
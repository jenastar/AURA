#!/usr/bin/env python3
"""
Test RAG Application using ChromaDB with Metrics
This simulates a real-world use case of a documentation Q&A system
"""

import os
import time
import uuid
import random
from datetime import datetime
from typing import List, Dict
import chromadb
from chromadb.utils import embedding_functions
from chromadb_wrapper import ChromaDBWrapper

# Sample documentation for our RAG system
SAMPLE_DOCS = [
    # Monitoring documentation
    {
        "id": "mon-001",
        "text": "Prometheus is a powerful open-source monitoring system that collects metrics from configured targets at given intervals.",
        "metadata": {"category": "monitoring", "tool": "prometheus"}
    },
    {
        "id": "mon-002", 
        "text": "Grafana is a visualization platform that works perfectly with Prometheus to create beautiful dashboards for your metrics.",
        "metadata": {"category": "monitoring", "tool": "grafana"}
    },
    {
        "id": "mon-003",
        "text": "Vector databases like ChromaDB store high-dimensional embeddings that enable semantic search capabilities.",
        "metadata": {"category": "monitoring", "tool": "chromadb"}
    },
    {
        "id": "mon-004",
        "text": "The AURA monitoring stack includes Prometheus, Grafana, and various exporters for comprehensive system monitoring.",
        "metadata": {"category": "monitoring", "tool": "aura"}
    },
    
    # AI/LLM documentation
    {
        "id": "ai-001",
        "text": "Large Language Models (LLMs) like GPT and Claude can generate human-like text and answer questions based on their training.",
        "metadata": {"category": "ai", "tool": "llm"}
    },
    {
        "id": "ai-002",
        "text": "RAG (Retrieval Augmented Generation) combines vector search with LLMs to provide accurate, context-aware responses.",
        "metadata": {"category": "ai", "tool": "rag"}
    },
    {
        "id": "ai-003",
        "text": "Embeddings are dense vector representations of text that capture semantic meaning for similarity search.",
        "metadata": {"category": "ai", "tool": "embeddings"}
    },
    {
        "id": "ai-004",
        "text": "Vector similarity search finds the most relevant documents by comparing embedding vectors using cosine similarity.",
        "metadata": {"category": "ai", "tool": "search"}
    },
    
    # Container documentation
    {
        "id": "container-001",
        "text": "Docker containers provide isolated environments for running applications with all their dependencies.",
        "metadata": {"category": "containers", "tool": "docker"}
    },
    {
        "id": "container-002",
        "text": "Docker Compose allows you to define and run multi-container applications with a simple YAML configuration.",
        "metadata": {"category": "containers", "tool": "docker-compose"}
    },
    {
        "id": "container-003",
        "text": "Container monitoring with cAdvisor provides resource usage and performance metrics for running containers.",
        "metadata": {"category": "containers", "tool": "cadvisor"}
    },
    {
        "id": "container-004",
        "text": "GPU containers require the NVIDIA Container Toolkit to access GPU resources from within Docker.",
        "metadata": {"category": "containers", "tool": "gpu"}
    }
]

# Sample queries that users might ask
SAMPLE_QUERIES = [
    "How do I monitor containers with Prometheus?",
    "What is RAG and how does it work?",
    "How can I visualize metrics in Grafana?",
    "What are embeddings used for?",
    "How do I set up GPU monitoring?",
    "What is the difference between Prometheus and Grafana?",
    "How does vector similarity search work?",
    "What tools are included in the AURA stack?",
    "How do I use Docker Compose?",
    "What is ChromaDB used for?"
]


class TestRAGApplication:
    """Simulated RAG application for documentation Q&A"""
    
    def __init__(self, chroma_host: str, chroma_port: int):
        print(f"Initializing RAG application with ChromaDB at {chroma_host}:{chroma_port}")
        
        # Initialize ChromaDB client
        self.client = chromadb.HttpClient(
            host=chroma_host,
            port=chroma_port
        )
        
        # Use sentence transformers for embeddings
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Initialize wrapper for metrics tracking
        self.db = ChromaDBWrapper(self.client, self.embedding_function)
        
        # Collection name
        self.collection_name = "documentation_qa"
        
        # Initialize the collection
        self._setup_collection()
    
    def _setup_collection(self):
        """Set up the vector database collection"""
        print("\nSetting up vector database collection...")
        
        try:
            # Delete existing collection if it exists
            try:
                self.client.delete_collection(self.collection_name)
                print(f"Deleted existing collection: {self.collection_name}")
            except:
                pass
            
            # Create new collection
            self.db.create_collection(
                name=self.collection_name,
                metadata={"description": "Documentation Q&A System"}
            )
            print(f"Created collection: {self.collection_name}")
            
            # Index all documents
            self._index_documents()
            
        except Exception as e:
            print(f"Error setting up collection: {e}")
    
    def _index_documents(self):
        """Index all sample documents"""
        print("\nIndexing documents...")
        
        # Prepare documents for batch insertion
        documents = [doc["text"] for doc in SAMPLE_DOCS]
        ids = [doc["id"] for doc in SAMPLE_DOCS]
        metadatas = [doc["metadata"] for doc in SAMPLE_DOCS]
        
        # Insert documents (this will be tracked by metrics)
        start_time = time.time()
        result = self.db.add_documents(
            collection_name=self.collection_name,
            documents=documents,
            metadata=metadatas,
            ids=ids
        )
        
        elapsed = time.time() - start_time
        print(f"Indexed {len(documents)} documents in {elapsed:.2f} seconds")
        print(f"Result: {result}")
        
        # Get collection stats
        stats = self.db.get_collection_stats(self.collection_name)
        print(f"Collection stats: {stats}")
    
    def search_documentation(self, query: str, top_k: int = 3) -> List[Dict]:
        """Search documentation using vector similarity"""
        print(f"\n🔍 Searching for: '{query}'")
        
        # Perform search (this will be tracked by metrics)
        start_time = time.time()
        results = self.db.search_documents(
            collection_name=self.collection_name,
            query=query,
            top_k=top_k
        )
        
        elapsed = time.time() - start_time
        print(f"Search completed in {elapsed:.3f} seconds")
        
        # Display results
        print(f"\nTop {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. Score: {result['score']:.3f}")
            print(f"   Text: {result['document'][:100]}...")
            print(f"   Metadata: {result.get('metadata', {})}")
        
        return results
    
    def simulate_user_queries(self, num_queries: int = 20, delay: float = 2.0):
        """Simulate users asking questions"""
        print(f"\n📊 Starting simulation of {num_queries} user queries...")
        print(f"   Delay between queries: {delay} seconds")
        
        for i in range(num_queries):
            # Pick a random query
            query = random.choice(SAMPLE_QUERIES)
            
            # Sometimes modify the query slightly
            if random.random() < 0.3:
                query = query.replace("?", "")
                query = f"Please explain {query.lower()}"
            
            print(f"\n{'='*60}")
            print(f"Query {i+1}/{num_queries} at {datetime.now().strftime('%H:%M:%S')}")
            
            # Perform search
            try:
                results = self.search_documentation(query, top_k=random.choice([3, 5, 10]))
                
                # Simulate processing the results (e.g., feeding to LLM)
                time.sleep(random.uniform(0.1, 0.5))
                
                # Occasionally add new documents
                if random.random() < 0.1:
                    self._add_random_document()
                
            except Exception as e:
                print(f"Error during search: {e}")
            
            # Wait before next query
            time.sleep(delay)
    
    def _add_random_document(self):
        """Add a random new document to the collection"""
        new_doc = {
            "id": f"dynamic-{uuid.uuid4().hex[:8]}",
            "text": f"This is a dynamically added document about {random.choice(['monitoring', 'AI', 'containers'])} created at {datetime.now()}",
            "metadata": {"category": "dynamic", "timestamp": datetime.now().isoformat()}
        }
        
        print(f"\n➕ Adding new document: {new_doc['id']}")
        
        self.db.add_documents(
            collection_name=self.collection_name,
            documents=[new_doc["text"]],
            metadata=[new_doc["metadata"]],
            ids=[new_doc["id"]]
        )
    
    def run_continuous_simulation(self):
        """Run continuous simulation for testing"""
        print("\n🚀 Starting continuous RAG simulation...")
        print("   This will simulate a real documentation Q&A system")
        print("   Press Ctrl+C to stop\n")
        
        iteration = 0
        try:
            while True:
                iteration += 1
                print(f"\n{'#'*60}")
                print(f"# Simulation Iteration {iteration}")
                print(f"{'#'*60}")
                
                # Run a batch of queries
                self.simulate_user_queries(
                    num_queries=random.randint(5, 10),
                    delay=random.uniform(1.0, 3.0)
                )
                
                # Occasionally rebuild the index
                if random.random() < 0.1:
                    print("\n🔧 Rebuilding index...")
                    self._setup_collection()
                
                # Show current stats
                stats = self.db.get_collection_stats(self.collection_name)
                print(f"\n📈 Current collection stats: {stats}")
                
                # Wait before next iteration
                print(f"\n💤 Waiting 30 seconds before next iteration...")
                time.sleep(30)
                
        except KeyboardInterrupt:
            print("\n\n✅ Simulation stopped by user")
            print("   Check Grafana dashboards to see the collected metrics!")


def main():
    # Get configuration from environment
    chroma_host = os.environ.get('CHROMADB_HOST', 'localhost')
    chroma_port = int(os.environ.get('CHROMADB_PORT', '8000'))
    
    # Create and run the test application
    app = TestRAGApplication(chroma_host, chroma_port)
    
    # Run continuous simulation
    app.run_continuous_simulation()


if __name__ == "__main__":
    main()
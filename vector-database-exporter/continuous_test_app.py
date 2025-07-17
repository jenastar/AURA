#!/usr/bin/env python3
"""
Continuous Test Application for Vector Database Metrics Generation
This app generates the metrics that dashboard panels expect to see
"""

import os
import time
import random
import requests
import json
from datetime import datetime
from typing import List

class VectorDBMetricsGenerator:
    """Generate vector database metrics by making API calls to ChromaDB and tracking operations"""
    
    def __init__(self, chromadb_host: str, chromadb_port: int):
        self.base_url = f"http://{chromadb_host}:{chromadb_port}/api/v1"
        self.collection_name = "continuous_test_collection"
        self.operation_count = 0
        
        print(f"Initializing metrics generator for ChromaDB at {self.base_url}")
        self._wait_for_chromadb()
        self._setup_collection()
    
    def _wait_for_chromadb(self, max_attempts=30):
        """Wait for ChromaDB to be ready"""
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"{self.base_url}/heartbeat", timeout=5)
                if response.status_code == 200:
                    print("✅ ChromaDB is ready")
                    return
            except requests.exceptions.RequestException:
                pass
            
            print(f"Waiting for ChromaDB... attempt {attempt + 1}/{max_attempts}")
            time.sleep(2)
        
        raise Exception("ChromaDB not available after waiting")
    
    def _setup_collection(self):
        """Set up test collection"""
        try:
            # Delete existing collection if it exists
            try:
                response = requests.delete(f"{self.base_url}/collections/{self.collection_name}")
                if response.status_code == 200:
                    print(f"Deleted existing collection: {self.collection_name}")
            except:
                pass
            
            # Create new collection
            collection_data = {
                "name": self.collection_name,
                "metadata": {"description": "Continuous testing collection"}
            }
            
            response = requests.post(
                f"{self.base_url}/collections",
                json=collection_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                print(f"✅ Created collection: {self.collection_name}")
            else:
                print(f"Failed to create collection: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Error setting up collection: {e}")
    
    def generate_random_embedding(self, dimension: int = 384) -> List[float]:
        """Generate a random embedding vector"""
        import math
        # Generate random vector
        vector = [random.gauss(0, 1) for _ in range(dimension)]
        # Normalize to unit vector
        magnitude = math.sqrt(sum(x*x for x in vector))
        return [x/magnitude for x in vector]
    
    def add_documents_batch(self, batch_size: int = 5):
        """Add a batch of documents with embeddings"""
        print(f"\n📝 Adding batch of {batch_size} documents...")
        
        start_time = time.time()
        
        # Generate documents and embeddings
        documents = []
        embeddings = []
        ids = []
        metadatas = []
        
        for i in range(batch_size):
            doc_id = f"doc_{self.operation_count}_{i}"
            doc_text = f"This is test document {self.operation_count}_{i} created at {datetime.now()}"
            embedding = self.generate_random_embedding()
            
            documents.append(doc_text)
            embeddings.append(embedding)
            ids.append(doc_id)
            metadatas.append({
                "batch": self.operation_count,
                "timestamp": datetime.now().isoformat(),
                "type": "continuous_test"
            })
        
        # Add to collection
        try:
            add_data = {
                "documents": documents,
                "embeddings": embeddings,
                "ids": ids,
                "metadatas": metadatas
            }
            
            response = requests.post(
                f"{self.base_url}/collections/{self.collection_name}/add",
                json=add_data,
                headers={"Content-Type": "application/json"}
            )
            
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                print(f"✅ Added {batch_size} documents in {elapsed:.2f}s")
                self.operation_count += 1
                return True
            else:
                print(f"❌ Failed to add documents: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error adding documents: {e}")
            return False
    
    def perform_similarity_search(self, query_text: str = None, n_results: int = 5):
        """Perform a similarity search"""
        if not query_text:
            query_text = f"Test query {self.operation_count} at {datetime.now()}"
        
        print(f"\n🔍 Performing similarity search: '{query_text[:50]}...'")
        
        start_time = time.time()
        
        try:
            # Generate query embedding
            query_embedding = self.generate_random_embedding()
            
            query_data = {
                "query_embeddings": [query_embedding],
                "n_results": n_results
            }
            
            response = requests.post(
                f"{self.base_url}/collections/{self.collection_name}/query",
                json=query_data,
                headers={"Content-Type": "application/json"}
            )
            
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                results = response.json()
                result_count = len(results.get('documents', [[]])[0])
                print(f"✅ Found {result_count} results in {elapsed:.3f}s")
                return True
            else:
                print(f"❌ Search failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error during search: {e}")
            return False
    
    def get_collection_stats(self):
        """Get collection statistics"""
        try:
            response = requests.get(f"{self.base_url}/collections/{self.collection_name}/count")
            if response.status_code == 200:
                count = response.json()
                print(f"📊 Collection has {count} documents")
                return count
            else:
                print(f"Failed to get collection count: {response.status_code}")
                return 0
        except Exception as e:
            print(f"Error getting collection stats: {e}")
            return 0
    
    def run_continuous_operations(self):
        """Run continuous vector operations to generate metrics"""
        print("\n🚀 Starting continuous vector operations...")
        print("This will generate metrics for the Grafana dashboard")
        print("Press Ctrl+C to stop\n")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                print(f"\n{'='*60}")
                print(f"Iteration {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}")
                
                # Add documents (generates embedding and insertion metrics)
                batch_size = random.randint(1, 8)
                self.add_documents_batch(batch_size)
                
                # Wait a bit
                time.sleep(1)
                
                # Perform searches (generates search metrics)
                num_searches = random.randint(2, 5)
                for search_num in range(num_searches):
                    search_terms = [
                        "test document about monitoring",
                        "vector database operations",
                        "continuous metrics generation",
                        "similarity search testing",
                        "ChromaDB performance analysis"
                    ]
                    query = random.choice(search_terms)
                    self.perform_similarity_search(query, random.randint(3, 10))
                    time.sleep(0.5)
                
                # Show stats
                count = self.get_collection_stats()
                
                # Wait before next iteration
                wait_time = random.uniform(10, 20)
                print(f"\n💤 Waiting {wait_time:.1f} seconds before next iteration...")
                time.sleep(wait_time)
                
        except KeyboardInterrupt:
            print("\n\n✅ Stopping continuous operations...")
            print("Check your Grafana dashboard - all panels should now show data!")

def main():
    # Get configuration from environment
    chromadb_host = os.environ.get('CHROMADB_HOST', 'localhost')
    chromadb_port = int(os.environ.get('CHROMADB_PORT', '8000'))
    
    print(f"Vector Database Metrics Generator")
    print(f"Target: {chromadb_host}:{chromadb_port}")
    print(f"Started at: {datetime.now()}")
    
    # Create and run the metrics generator
    generator = VectorDBMetricsGenerator(chromadb_host, chromadb_port)
    generator.run_continuous_operations()

if __name__ == "__main__":
    main()
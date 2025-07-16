#!/usr/bin/env python3
"""
ChromaDB Wrapper with Metrics Integration
Provides transparent metrics collection for ChromaDB operations
"""

import uuid
import time
from typing import List, Dict, Optional, Any
from vector_db_metrics_exporter import VectorDatabaseWrapper, VectorDatabaseMetricsTracker


class ChromaDBWrapper(VectorDatabaseWrapper):
    """ChromaDB wrapper with integrated metrics tracking"""
    
    def __init__(self, chroma_client, embedding_function=None):
        self.chroma_client = chroma_client
        self.embedding_function = embedding_function
        tracker = VectorDatabaseMetricsTracker("chromadb")
        super().__init__("chromadb", chroma_client, tracker)
        
    def _generate_embeddings(self, documents: List[str], model: str = "default", **kwargs):
        """Generate embeddings using ChromaDB's embedding function"""
        if self.embedding_function:
            return self.embedding_function(documents)
        else:
            # Fallback to simple tokenization if no embedding function
            return [[hash(doc) % 1000 / 1000.0 for _ in range(768)] for doc in documents]
    
    def _perform_search(self, query_vector: List[float], collection_name: str, top_k: int = 10, 
                       search_type: str = "cosine", **kwargs):
        """Perform similarity search in ChromaDB"""
        try:
            collection = self.chroma_client.get_collection(collection_name)
            
            # ChromaDB expects query embeddings as a list of lists
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                **kwargs
            )
            
            # Format results to match our wrapper interface
            formatted_results = []
            if results['documents'] and results['distances']:
                for i, (doc, distance) in enumerate(zip(results['documents'][0], results['distances'][0])):
                    # Convert distance to similarity score (assuming cosine distance)
                    score = 1.0 - distance if search_type == "cosine" else distance
                    formatted_results.append({
                        'document': doc,
                        'score': score,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'id': results['ids'][0][i] if results['ids'] else f"doc_{i}"
                    })
            
            return formatted_results
            
        except Exception as e:
            print(f"Error in ChromaDB search: {e}")
            raise
    
    def _insert_vectors(self, vectors: List[List[float]], collection_name: str, 
                       metadata: Optional[List[dict]] = None, documents: Optional[List[str]] = None, 
                       ids: Optional[List[str]] = None, **kwargs):
        """Insert vectors into ChromaDB collection"""
        try:
            collection = self.chroma_client.get_or_create_collection(collection_name)
            
            # Generate IDs if not provided
            if not ids:
                ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
            
            # Add vectors to collection
            collection.add(
                embeddings=vectors,
                metadatas=metadata,
                documents=documents,
                ids=ids
            )
            
            return {"inserted_count": len(vectors), "ids": ids}
            
        except Exception as e:
            print(f"Error inserting into ChromaDB: {e}")
            raise
    
    def _build_index(self, collection_name: str, index_type: str = "hnsw", **kwargs):
        """ChromaDB handles indexing automatically, but we can track collection creation"""
        try:
            collection = self.chroma_client.get_or_create_collection(
                collection_name,
                metadata={"index_type": index_type, **kwargs}
            )
            return {"status": "created", "collection": collection_name}
            
        except Exception as e:
            print(f"Error creating ChromaDB collection: {e}")
            raise
    
    def create_collection(self, name: str, metadata: Optional[dict] = None, embedding_function=None):
        """Create a new collection with metrics tracking"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'collection_creation',
                name,
                metadata=metadata or {}
            )
            
            collection = self.chroma_client.create_collection(
                name=name,
                metadata=metadata,
                embedding_function=embedding_function or self.embedding_function
            )
            
            self.tracker.end_operation(operation_id, success=True)
            return collection
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id,
                success=False,
                error_type=type(e).__name__
            )
            raise
    
    def delete_collection(self, name: str):
        """Delete a collection with metrics tracking"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'collection_deletion',
                name
            )
            
            self.chroma_client.delete_collection(name)
            
            self.tracker.end_operation(operation_id, success=True)
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id,
                success=False,
                error_type=type(e).__name__
            )
            raise
    
    def add_documents(self, collection_name: str, documents: List[str], 
                     metadata: Optional[List[dict]] = None, ids: Optional[List[str]] = None):
        """Add documents to collection with automatic embedding and metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'document_addition',
                collection_name,
                batch_size=len(documents)
            )
            
            # Generate embeddings
            embeddings = self._generate_embeddings(documents)
            
            # Insert vectors
            result = self._insert_vectors(
                vectors=embeddings,
                collection_name=collection_name,
                metadata=metadata,
                documents=documents,
                ids=ids
            )
            
            self.tracker.end_operation(operation_id, success=True)
            return result
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id,
                success=False,
                error_type=type(e).__name__
            )
            raise
    
    def search_documents(self, collection_name: str, query: str, top_k: int = 10, **kwargs):
        """Search documents by query text with metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'document_search',
                collection_name,
                top_k=top_k
            )
            
            # Generate query embedding
            query_embedding = self._generate_embeddings([query])[0]
            
            # Perform search
            results = self._perform_search(
                query_vector=query_embedding,
                collection_name=collection_name,
                top_k=top_k,
                **kwargs
            )
            
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
    
    def get_collection_stats(self, collection_name: str):
        """Get collection statistics with metrics updates"""
        try:
            collection = self.chroma_client.get_collection(collection_name)
            count = collection.count()
            
            # Update metrics
            self.tracker.update_collection_stats(collection_name, count, 768)  # Assume 768 dimensions
            
            return {
                "name": collection_name,
                "count": count,
                "dimension": 768
            }
            
        except Exception as e:
            print(f"Error getting ChromaDB collection stats: {e}")
            return {"error": str(e)}


def demo_chromadb():
    """Demo function for testing ChromaDB wrapper"""
    try:
        import chromadb
        from chromadb.config import Settings
        
        # Create in-memory ChromaDB client for demo
        client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=None  # In-memory
        ))
        
        # Create wrapper
        wrapper = ChromaDBWrapper(client)
        
        # Demo operations
        print("Creating collection...")
        wrapper.create_collection("demo_collection")
        
        print("Adding documents...")
        documents = [
            "ChromaDB is a vector database for AI applications",
            "Vector databases store high-dimensional embeddings",
            "Similarity search finds the most relevant documents",
            "Machine learning models generate embeddings from text",
            "RAG systems use vector databases for knowledge retrieval"
        ]
        
        wrapper.add_documents("demo_collection", documents)
        
        print("Searching documents...")
        results = wrapper.search_documents("demo_collection", "What is a vector database?", top_k=3)
        
        for i, result in enumerate(results):
            print(f"Result {i+1}: {result['document'][:50]}... (score: {result['score']:.3f})")
        
        print("Getting collection stats...")
        stats = wrapper.get_collection_stats("demo_collection")
        print(f"Collection stats: {stats}")
        
        return wrapper
        
    except ImportError:
        print("ChromaDB not installed. Install with: pip install chromadb")
        return None
    except Exception as e:
        print(f"Demo error: {e}")
        return None


if __name__ == "__main__":
    demo_chromadb()
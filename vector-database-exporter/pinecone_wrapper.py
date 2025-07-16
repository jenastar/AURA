#!/usr/bin/env python3
"""
Pinecone Wrapper with Metrics Integration
Provides transparent metrics collection for Pinecone operations
"""

import uuid
import time
from typing import List, Dict, Optional, Any, Tuple
from vector_db_metrics_exporter import VectorDatabaseWrapper, VectorDatabaseMetricsTracker


class PineconeWrapper(VectorDatabaseWrapper):
    """Pinecone wrapper with integrated metrics tracking"""
    
    def __init__(self, pinecone_index, embedding_function=None):
        self.pinecone_index = pinecone_index
        self.embedding_function = embedding_function
        tracker = VectorDatabaseMetricsTracker("pinecone")
        super().__init__("pinecone", pinecone_index, tracker)
        
    def _generate_embeddings(self, documents: List[str], model: str = "default", **kwargs):
        """Generate embeddings for documents"""
        if self.embedding_function:
            return self.embedding_function(documents)
        else:
            # Fallback to simple hash-based embeddings for demo
            import hashlib
            embeddings = []
            for doc in documents:
                # Create a deterministic embedding from document hash
                hash_obj = hashlib.md5(doc.encode())
                hash_hex = hash_obj.hexdigest()
                # Convert hex to float values between -1 and 1
                embedding = []
                for i in range(0, len(hash_hex), 2):
                    val = int(hash_hex[i:i+2], 16) / 127.5 - 1.0
                    embedding.append(val)
                # Pad or truncate to desired dimension
                while len(embedding) < 1536:  # Common OpenAI dimension
                    embedding.extend(embedding[:min(len(embedding), 1536 - len(embedding))])
                embeddings.append(embedding[:1536])
            return embeddings
    
    def _perform_search(self, query_vector: List[float], collection_name: str = "default", 
                       top_k: int = 10, search_type: str = "cosine", **kwargs):
        """Perform similarity search in Pinecone"""
        try:
            # Pinecone search
            search_kwargs = {
                'vector': query_vector,
                'top_k': top_k,
                'include_metadata': True,
                'include_values': False
            }
            
            # Add namespace if specified
            if collection_name != "default":
                search_kwargs['namespace'] = collection_name
            
            # Add any additional filters
            if 'filter' in kwargs:
                search_kwargs['filter'] = kwargs['filter']
            
            response = self.pinecone_index.query(**search_kwargs)
            
            # Format results to match our wrapper interface
            formatted_results = []
            for match in response.get('matches', []):
                formatted_results.append({
                    'id': match.get('id'),
                    'score': match.get('score', 0.0),
                    'metadata': match.get('metadata', {}),
                    'document': match.get('metadata', {}).get('text', '')
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"Error in Pinecone search: {e}")
            raise
    
    def _insert_vectors(self, vectors: List[List[float]], collection_name: str = "default", 
                       metadata: Optional[List[dict]] = None, documents: Optional[List[str]] = None,
                       ids: Optional[List[str]] = None, **kwargs):
        """Insert vectors into Pinecone index"""
        try:
            # Generate IDs if not provided
            if not ids:
                ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
            
            # Prepare upsert data
            upsert_data = []
            for i, vector in enumerate(vectors):
                item = {
                    'id': ids[i],
                    'values': vector
                }
                
                # Add metadata if provided
                if metadata and i < len(metadata):
                    item['metadata'] = metadata[i].copy()
                else:
                    item['metadata'] = {}
                
                # Add document text to metadata if provided
                if documents and i < len(documents):
                    item['metadata']['text'] = documents[i]
                
                upsert_data.append(item)
            
            # Upsert to Pinecone
            upsert_kwargs = {'vectors': upsert_data}
            if collection_name != "default":
                upsert_kwargs['namespace'] = collection_name
            
            response = self.pinecone_index.upsert(**upsert_kwargs)
            
            return {
                "inserted_count": response.get('upserted_count', len(vectors)),
                "ids": ids
            }
            
        except Exception as e:
            print(f"Error inserting into Pinecone: {e}")
            raise
    
    def _build_index(self, collection_name: str = "default", index_type: str = "cosine", **kwargs):
        """Pinecone handles indexing automatically"""
        # Pinecone automatically indexes vectors, so this is mostly a no-op
        # But we can use it to track when we're working with different namespaces
        return {"status": "auto_indexed", "namespace": collection_name, "metric": index_type}
    
    def upsert_documents(self, documents: List[str], namespace: str = "default",
                        metadata: Optional[List[dict]] = None, ids: Optional[List[str]] = None,
                        model: str = "default"):
        """Upsert documents with automatic embedding and metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'document_upsert',
                namespace,
                batch_size=len(documents),
                model=model
            )
            
            # Generate embeddings
            embeddings = self._generate_embeddings(documents, model)
            
            # Insert vectors
            result = self._insert_vectors(
                vectors=embeddings,
                collection_name=namespace,
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
    
    def search_documents(self, query: str, namespace: str = "default", top_k: int = 10, 
                        filter_dict: Optional[dict] = None, model: str = "default"):
        """Search documents by query text with metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'document_search',
                namespace,
                top_k=top_k,
                model=model
            )
            
            # Generate query embedding
            query_embedding = self._generate_embeddings([query], model)[0]
            
            # Perform search
            results = self._perform_search(
                query_vector=query_embedding,
                collection_name=namespace,
                top_k=top_k,
                filter=filter_dict
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
    
    def delete_vectors(self, ids: List[str], namespace: str = "default"):
        """Delete vectors by IDs with metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'vector_deletion',
                namespace,
                batch_size=len(ids)
            )
            
            delete_kwargs = {'ids': ids}
            if namespace != "default":
                delete_kwargs['namespace'] = namespace
            
            response = self.pinecone_index.delete(**delete_kwargs)
            
            self.tracker.end_operation(operation_id, success=True)
            return response
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id,
                success=False,
                error_type=type(e).__name__
            )
            raise
    
    def get_index_stats(self):
        """Get index statistics with metrics updates"""
        try:
            stats = self.pinecone_index.describe_index_stats()
            
            # Update metrics for default namespace
            total_count = stats.get('total_vector_count', 0)
            dimension = stats.get('dimension', 0)
            self.tracker.update_collection_stats("default", total_count, dimension)
            
            # Update metrics for each namespace
            namespaces = stats.get('namespaces', {})
            for namespace, ns_stats in namespaces.items():
                count = ns_stats.get('vector_count', 0)
                self.tracker.update_collection_stats(namespace, count, dimension)
            
            return stats
            
        except Exception as e:
            print(f"Error getting Pinecone index stats: {e}")
            return {"error": str(e)}
    
    def fetch_vectors(self, ids: List[str], namespace: str = "default"):
        """Fetch vectors by IDs with metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'vector_fetch',
                namespace,
                batch_size=len(ids)
            )
            
            fetch_kwargs = {'ids': ids}
            if namespace != "default":
                fetch_kwargs['namespace'] = namespace
            
            response = self.pinecone_index.fetch(**fetch_kwargs)
            
            self.tracker.end_operation(operation_id, success=True)
            return response
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id,
                success=False,
                error_type=type(e).__name__
            )
            raise


def demo_pinecone():
    """Demo function for testing Pinecone wrapper (requires mock since we don't have real Pinecone)"""
    print("Pinecone demo requires actual Pinecone API key and index.")
    print("To use this wrapper:")
    print("1. Install pinecone: pip install pinecone-client")
    print("2. Set PINECONE_API_KEY environment variable")
    print("3. Create a Pinecone index")
    print("4. Initialize wrapper like this:")
    print("""
import pinecone
import os

pinecone.init(
    api_key=os.environ['PINECONE_API_KEY'],
    environment='your-environment'
)

index = pinecone.Index('your-index-name')
wrapper = PineconeWrapper(index)

# Use wrapper methods
wrapper.upsert_documents(['doc1', 'doc2'])
results = wrapper.search_documents('query text')
    """)
    
    # Create a mock wrapper for demonstration
    class MockPineconeIndex:
        def query(self, **kwargs):
            return {
                'matches': [
                    {'id': 'doc1', 'score': 0.95, 'metadata': {'text': 'Sample document 1'}},
                    {'id': 'doc2', 'score': 0.88, 'metadata': {'text': 'Sample document 2'}}
                ]
            }
        
        def upsert(self, **kwargs):
            return {'upserted_count': len(kwargs.get('vectors', []))}
        
        def describe_index_stats(self):
            return {
                'total_vector_count': 1000,
                'dimension': 1536,
                'namespaces': {
                    'default': {'vector_count': 1000}
                }
            }
    
    # Demo with mock
    print("\nRunning demo with mock Pinecone index...")
    mock_index = MockPineconeIndex()
    wrapper = PineconeWrapper(mock_index)
    
    # Demo operations
    print("Upserting documents...")
    documents = [
        "Pinecone is a managed vector database service",
        "Vector search enables semantic similarity matching",
        "Embeddings capture semantic meaning of text",
        "RAG applications use vector databases for retrieval",
        "Machine learning models create dense vector representations"
    ]
    
    result = wrapper.upsert_documents(documents, namespace="demo")
    print(f"Upserted {result['inserted_count']} documents")
    
    print("Searching documents...")
    results = wrapper.search_documents("What is Pinecone?", namespace="demo", top_k=3)
    
    for i, result in enumerate(results):
        print(f"Result {i+1}: {result['document'][:50]}... (score: {result['score']:.3f})")
    
    print("Getting index stats...")
    stats = wrapper.get_index_stats()
    print(f"Index stats: {stats}")
    
    return wrapper


if __name__ == "__main__":
    demo_pinecone()
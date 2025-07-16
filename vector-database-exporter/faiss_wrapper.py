#!/usr/bin/env python3
"""
FAISS Wrapper with Metrics Integration
Provides transparent metrics collection for FAISS operations
"""

import uuid
import time
import numpy as np
import pickle
import os
from typing import List, Dict, Optional, Any, Tuple
from vector_db_metrics_exporter import VectorDatabaseWrapper, VectorDatabaseMetricsTracker


class FAISSWrapper(VectorDatabaseWrapper):
    """FAISS wrapper with integrated metrics tracking"""
    
    def __init__(self, dimension: int = 768, index_type: str = "flat", embedding_function=None):
        self.dimension = dimension
        self.index_type = index_type
        self.embedding_function = embedding_function
        self.indices: Dict[str, Any] = {}  # collection_name -> faiss_index
        self.metadata_store: Dict[str, Dict[str, Any]] = {}  # collection_name -> {id -> metadata}
        self.document_store: Dict[str, Dict[str, str]] = {}  # collection_name -> {id -> document}
        self.id_mapping: Dict[str, List[str]] = {}  # collection_name -> [ids_in_order]
        
        tracker = VectorDatabaseMetricsTracker("faiss")
        super().__init__("faiss", self.indices, tracker)
        
        # Import FAISS
        try:
            import faiss
            self.faiss = faiss
        except ImportError:
            print("FAISS not installed. Install with: pip install faiss-cpu or pip install faiss-gpu")
            self.faiss = None
    
    def _create_index(self, collection_name: str, dimension: int = None, index_type: str = None):
        """Create a new FAISS index"""
        if not self.faiss:
            raise ImportError("FAISS not available")
        
        dimension = dimension or self.dimension
        index_type = index_type or self.index_type
        
        if index_type == "flat":
            index = self.faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)
        elif index_type == "hnsw":
            index = self.faiss.IndexHNSWFlat(dimension, 32)
        elif index_type == "ivf":
            quantizer = self.faiss.IndexFlatIP(dimension)
            index = self.faiss.IndexIVFFlat(quantizer, dimension, 100)
        else:
            # Default to flat
            index = self.faiss.IndexFlatIP(dimension)
        
        self.indices[collection_name] = index
        self.metadata_store[collection_name] = {}
        self.document_store[collection_name] = {}
        self.id_mapping[collection_name] = []
        
        return index
    
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
                while len(embedding) < self.dimension:
                    embedding.extend(embedding[:min(len(embedding), self.dimension - len(embedding))])
                embeddings.append(embedding[:self.dimension])
            return embeddings
    
    def _perform_search(self, query_vector: List[float], collection_name: str, 
                       top_k: int = 10, search_type: str = "cosine", **kwargs):
        """Perform similarity search in FAISS"""
        try:
            if collection_name not in self.indices:
                raise ValueError(f"Collection {collection_name} does not exist")
            
            index = self.indices[collection_name]
            query_array = np.array([query_vector], dtype=np.float32)
            
            # Normalize for cosine similarity if using IP index
            if search_type == "cosine":
                self.faiss.normalize_L2(query_array)
            
            # Search
            scores, indices = index.search(query_array, top_k)
            
            # Format results
            results = []
            for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                if idx == -1:  # FAISS returns -1 for invalid indices
                    continue
                
                # Get document ID
                doc_id = self.id_mapping[collection_name][idx] if idx < len(self.id_mapping[collection_name]) else f"doc_{idx}"
                
                result = {
                    'id': doc_id,
                    'score': float(score),
                    'metadata': self.metadata_store[collection_name].get(doc_id, {}),
                    'document': self.document_store[collection_name].get(doc_id, '')
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Error in FAISS search: {e}")
            raise
    
    def _insert_vectors(self, vectors: List[List[float]], collection_name: str, 
                       metadata: Optional[List[dict]] = None, documents: Optional[List[str]] = None,
                       ids: Optional[List[str]] = None, **kwargs):
        """Insert vectors into FAISS index"""
        try:
            if collection_name not in self.indices:
                self._create_index(collection_name)
            
            index = self.indices[collection_name]
            
            # Convert to numpy array
            vectors_array = np.array(vectors, dtype=np.float32)
            
            # Normalize for cosine similarity if using IP index
            self.faiss.normalize_L2(vectors_array)
            
            # Generate IDs if not provided
            if not ids:
                ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
            
            # Store metadata and documents
            for i, vector_id in enumerate(ids):
                if metadata and i < len(metadata):
                    self.metadata_store[collection_name][vector_id] = metadata[i]
                if documents and i < len(documents):
                    self.document_store[collection_name][vector_id] = documents[i]
                
                self.id_mapping[collection_name].append(vector_id)
            
            # Add to index
            index.add(vectors_array)
            
            return {
                "inserted_count": len(vectors),
                "ids": ids
            }
            
        except Exception as e:
            print(f"Error inserting into FAISS: {e}")
            raise
    
    def _build_index(self, collection_name: str, index_type: str = "default", **kwargs):
        """Build or train FAISS index"""
        try:
            if collection_name not in self.indices:
                raise ValueError(f"Collection {collection_name} does not exist")
            
            index = self.indices[collection_name]
            
            # Train index if needed (for IVF indices)
            if hasattr(index, 'is_trained') and not index.is_trained:
                if index.ntotal > 0:
                    # Get all vectors for training
                    all_vectors = []
                    for i in range(index.ntotal):
                        vector = index.reconstruct(i)
                        all_vectors.append(vector)
                    
                    training_data = np.array(all_vectors, dtype=np.float32)
                    index.train(training_data)
            
            return {"status": "trained" if hasattr(index, 'is_trained') and index.is_trained else "ready"}
            
        except Exception as e:
            print(f"Error building FAISS index: {e}")
            raise
    
    def create_collection(self, name: str, dimension: int = None, index_type: str = None, 
                         metadata: Optional[dict] = None):
        """Create a new collection with metrics tracking"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'collection_creation',
                name,
                index_type=index_type or self.index_type,
                dimension=dimension or self.dimension
            )
            
            index = self._create_index(name, dimension, index_type)
            
            self.tracker.end_operation(operation_id, success=True)
            return index
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id,
                success=False,
                error_type=type(e).__name__
            )
            raise
    
    def add_documents(self, collection_name: str, documents: List[str], 
                     metadata: Optional[List[dict]] = None, ids: Optional[List[str]] = None,
                     model: str = "default"):
        """Add documents to collection with automatic embedding and metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'document_addition',
                collection_name,
                batch_size=len(documents),
                model=model
            )
            
            # Generate embeddings
            embeddings = self._generate_embeddings(documents, model)
            
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
    
    def search_documents(self, collection_name: str, query: str, top_k: int = 10, 
                        search_type: str = "cosine", model: str = "default"):
        """Search documents by query text with metrics"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'document_search',
                collection_name,
                top_k=top_k,
                search_type=search_type,
                model=model
            )
            
            # Generate query embedding
            query_embedding = self._generate_embeddings([query], model)[0]
            
            # Perform search
            results = self._perform_search(
                query_vector=query_embedding,
                collection_name=collection_name,
                top_k=top_k,
                search_type=search_type
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
            if collection_name not in self.indices:
                return {"error": f"Collection {collection_name} does not exist"}
            
            index = self.indices[collection_name]
            count = index.ntotal
            dimension = index.d
            
            # Update metrics
            self.tracker.update_collection_stats(collection_name, count, dimension)
            
            # Estimate memory usage
            memory_bytes = count * dimension * 4  # Assuming float32
            self.tracker.update_memory_usage(collection_name, self.index_type, memory_bytes)
            
            return {
                "name": collection_name,
                "count": count,
                "dimension": dimension,
                "index_type": self.index_type,
                "is_trained": getattr(index, 'is_trained', True),
                "memory_bytes": memory_bytes
            }
            
        except Exception as e:
            print(f"Error getting FAISS collection stats: {e}")
            return {"error": str(e)}
    
    def save_collection(self, collection_name: str, filepath: str):
        """Save collection to disk"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'collection_save',
                collection_name
            )
            
            if collection_name not in self.indices:
                raise ValueError(f"Collection {collection_name} does not exist")
            
            # Save FAISS index
            index_path = f"{filepath}.faiss"
            self.faiss.write_index(self.indices[collection_name], index_path)
            
            # Save metadata and documents
            metadata_path = f"{filepath}.metadata"
            with open(metadata_path, 'wb') as f:
                pickle.dump({
                    'metadata': self.metadata_store[collection_name],
                    'documents': self.document_store[collection_name],
                    'id_mapping': self.id_mapping[collection_name],
                    'dimension': self.dimension,
                    'index_type': self.index_type
                }, f)
            
            self.tracker.end_operation(operation_id, success=True)
            return {"saved": True, "index_path": index_path, "metadata_path": metadata_path}
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id,
                success=False,
                error_type=type(e).__name__
            )
            raise
    
    def load_collection(self, collection_name: str, filepath: str):
        """Load collection from disk"""
        operation_id = str(uuid.uuid4())
        
        try:
            self.tracker.start_operation(
                operation_id,
                'collection_load',
                collection_name
            )
            
            # Load FAISS index
            index_path = f"{filepath}.faiss"
            index = self.faiss.read_index(index_path)
            self.indices[collection_name] = index
            
            # Load metadata and documents
            metadata_path = f"{filepath}.metadata"
            with open(metadata_path, 'rb') as f:
                data = pickle.load(f)
                self.metadata_store[collection_name] = data.get('metadata', {})
                self.document_store[collection_name] = data.get('documents', {})
                self.id_mapping[collection_name] = data.get('id_mapping', [])
            
            self.tracker.end_operation(operation_id, success=True)
            return {"loaded": True, "collection": collection_name}
            
        except Exception as e:
            self.tracker.end_operation(
                operation_id,
                success=False,
                error_type=type(e).__name__
            )
            raise


def demo_faiss():
    """Demo function for testing FAISS wrapper"""
    try:
        # Create wrapper
        wrapper = FAISSWrapper(dimension=384, index_type="flat")
        
        print("Creating collection...")
        wrapper.create_collection("demo_collection", dimension=384, index_type="flat")
        
        print("Adding documents...")
        documents = [
            "FAISS is a library for efficient similarity search",
            "Vector databases enable semantic search capabilities",
            "Similarity search finds the most relevant documents",
            "Machine learning models create vector embeddings",
            "RAG systems use vector search for retrieval"
        ]
        
        result = wrapper.add_documents("demo_collection", documents)
        print(f"Added {result['inserted_count']} documents")
        
        print("Searching documents...")
        results = wrapper.search_documents("demo_collection", "What is FAISS?", top_k=3)
        
        for i, result in enumerate(results):
            print(f"Result {i+1}: {result['document'][:50]}... (score: {result['score']:.3f})")
        
        print("Getting collection stats...")
        stats = wrapper.get_collection_stats("demo_collection")
        print(f"Collection stats: {stats}")
        
        # Test saving and loading
        print("Saving collection...")
        save_result = wrapper.save_collection("demo_collection", "/tmp/demo_faiss")
        print(f"Save result: {save_result}")
        
        print("Loading collection as new collection...")
        wrapper.load_collection("loaded_collection", "/tmp/demo_faiss")
        
        loaded_stats = wrapper.get_collection_stats("loaded_collection")
        print(f"Loaded collection stats: {loaded_stats}")
        
        return wrapper
        
    except ImportError:
        print("FAISS not installed. Install with: pip install faiss-cpu")
        return None
    except Exception as e:
        print(f"Demo error: {e}")
        return None


if __name__ == "__main__":
    demo_faiss()
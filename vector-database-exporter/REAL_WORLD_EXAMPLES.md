# Vector Database Monitoring - Real World Examples

This document contains practical, executable examples that demonstrate vector database monitoring in real scenarios. Each example can be run directly and will generate actual metrics visible in Grafana.

## Prerequisites

1. Ensure ChromaDB is running:
```bash
docker compose -f chromadb-compose.yml up -d
```

2. Ensure vector exporter is in real mode:
```bash
DEMO_MODE=false docker compose up -d vector_db_exporter
```

3. Check ChromaDB is accessible:
```bash
curl http://localhost:8000/api/v1/heartbeat
```

## Example 1: Document Knowledge Base with RAG

This example shows how to monitor a document-based Q&A system.

### Code: `example1_document_rag.py`

```python
#!/usr/bin/env python3
"""
Example 1: Document Knowledge Base RAG System
Monitors document indexing and retrieval for a technical documentation system
"""

import chromadb
from chromadb.utils import embedding_functions
import time
import sys
sys.path.append('/app')  # For Docker
try:
    from chromadb_wrapper import ChromaDBWrapper
except:
    # If running locally, adjust path
    sys.path.append('.')
    from chromadb_wrapper import ChromaDBWrapper

# Technical documentation samples
TECHNICAL_DOCS = [
    {
        "id": "docker-001",
        "content": "Docker containers package applications with their dependencies, ensuring consistency across different environments. Use 'docker run' to start containers and 'docker build' to create images from Dockerfiles.",
        "metadata": {"category": "docker", "type": "basics", "difficulty": "beginner"}
    },
    {
        "id": "k8s-001",
        "content": "Kubernetes orchestrates containerized applications across clusters. Pods are the smallest deployable units, while Services provide network access to pods. Deployments manage the desired state of your applications.",
        "metadata": {"category": "kubernetes", "type": "concepts", "difficulty": "intermediate"}
    },
    {
        "id": "prometheus-001",
        "content": "Prometheus scrapes metrics from configured targets using a pull model. Metrics are stored in a time-series database and can be queried using PromQL. Use recording rules to precompute frequently needed expressions.",
        "metadata": {"category": "monitoring", "type": "metrics", "difficulty": "intermediate"}
    },
    {
        "id": "grafana-001",
        "content": "Grafana visualizes metrics from various data sources including Prometheus. Create dashboards with panels showing graphs, gauges, and tables. Use variables to make dashboards dynamic and reusable.",
        "metadata": {"category": "monitoring", "type": "visualization", "difficulty": "beginner"}
    },
    {
        "id": "python-001",
        "content": "Python decorators modify function behavior without changing the function code. Use @property for getters/setters, @staticmethod for methods that don't need self, and @classmethod for factory methods.",
        "metadata": {"category": "programming", "type": "python", "difficulty": "intermediate"}
    }
]

def run_document_rag_example():
    """Demonstrates document indexing and retrieval with monitoring"""
    
    print("=" * 60)
    print("Example 1: Document Knowledge Base RAG System")
    print("=" * 60)
    
    # Initialize ChromaDB with monitoring
    client = chromadb.HttpClient(host="localhost", port=8000)
    
    # Use sentence transformers for better embeddings
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    # Create monitored wrapper
    db = ChromaDBWrapper(client, embedding_fn)
    
    # 1. Create collection for technical docs
    collection_name = "technical_documentation"
    print(f"\n1. Creating collection: {collection_name}")
    
    try:
        client.delete_collection(collection_name)
    except:
        pass
    
    db.create_collection(
        name=collection_name,
        metadata={"description": "Technical documentation knowledge base"}
    )
    
    # 2. Index documents (generates embedding and insertion metrics)
    print("\n2. Indexing technical documentation...")
    start_time = time.time()
    
    result = db.add_documents(
        collection_name=collection_name,
        documents=[doc["content"] for doc in TECHNICAL_DOCS],
        metadata=[doc["metadata"] for doc in TECHNICAL_DOCS],
        ids=[doc["id"] for doc in TECHNICAL_DOCS]
    )
    
    indexing_time = time.time() - start_time
    print(f"   Indexed {len(TECHNICAL_DOCS)} documents in {indexing_time:.2f} seconds")
    print(f"   Result: {result}")
    
    # 3. Perform various searches (generates search metrics)
    queries = [
        "How do I create a Docker container?",
        "What is Kubernetes used for?",
        "How to visualize Prometheus metrics?",
        "Explain Python decorators",
        "What is the difference between Docker and Kubernetes?"
    ]
    
    print("\n3. Performing searches...")
    for i, query in enumerate(queries, 1):
        print(f"\n   Query {i}: {query}")
        
        start_time = time.time()
        results = db.search_documents(
            collection_name=collection_name,
            query=query,
            top_k=3
        )
        search_time = time.time() - start_time
        
        print(f"   Search completed in {search_time:.3f} seconds")
        print(f"   Top result: {results[0]['document'][:80]}...")
        print(f"   Similarity score: {results[0]['score']:.3f}")
    
    # 4. Get collection statistics
    print("\n4. Collection Statistics:")
    stats = db.get_collection_stats(collection_name)
    print(f"   {stats}")
    
    print("\n✅ Example 1 complete! Check Grafana for metrics.")
    print("   - Embedding generation time")
    print("   - Vector insertion count and latency")
    print("   - Search performance and similarity scores")
    
    return db, collection_name


if __name__ == "__main__":
    run_document_rag_example()
```

### Running the Example

```bash
# Option 1: Run in Docker container
docker exec -it mon_vector_db_exporter python -c "$(cat example1_document_rag.py)"

# Option 2: Run locally (requires chromadb and dependencies)
pip install chromadb sentence-transformers
python example1_document_rag.py
```

### Metrics Generated

- `vector_db_embeddings_generated_total`: 5 documents embedded
- `vector_db_insertions_total`: 5 vectors inserted
- `vector_db_similarity_searches_total`: 5 searches performed
- `vector_db_similarity_scores`: Distribution of relevance scores

## Example 2: Image Similarity Search System

This example demonstrates monitoring for an image search system using vector embeddings.

### Code: `example2_image_search.py`

```python
#!/usr/bin/env python3
"""
Example 2: Image Similarity Search System
Monitors image embedding and similarity search for a photo management system
"""

import chromadb
import numpy as np
import time
import sys
sys.path.append('/app')  # For Docker
try:
    from chromadb_wrapper import ChromaDBWrapper
except:
    sys.path.append('.')
    from chromadb_wrapper import ChromaDBWrapper

# Simulated image data (in real system, these would be actual image embeddings)
SAMPLE_IMAGES = [
    {
        "id": "img_001",
        "description": "Golden retriever playing in park",
        "metadata": {"category": "animals", "tags": ["dog", "outdoor", "pet"], "size": "1920x1080"}
    },
    {
        "id": "img_002", 
        "description": "Mountain landscape at sunset",
        "metadata": {"category": "nature", "tags": ["landscape", "mountain", "sunset"], "size": "4000x3000"}
    },
    {
        "id": "img_003",
        "description": "Modern office building with glass facade",
        "metadata": {"category": "architecture", "tags": ["building", "urban", "modern"], "size": "3000x2000"}
    },
    {
        "id": "img_004",
        "description": "Fresh vegetables on wooden table",
        "metadata": {"category": "food", "tags": ["vegetables", "healthy", "cooking"], "size": "2500x1667"}
    },
    {
        "id": "img_005",
        "description": "Beach with palm trees and blue water",
        "metadata": {"category": "nature", "tags": ["beach", "tropical", "vacation"], "size": "3840x2160"}
    },
    {
        "id": "img_006",
        "description": "Cat sleeping on windowsill",
        "metadata": {"category": "animals", "tags": ["cat", "indoor", "pet"], "size": "2000x1333"}
    },
    {
        "id": "img_007",
        "description": "City skyline at night with lights",
        "metadata": {"category": "urban", "tags": ["city", "night", "lights"], "size": "4096x2304"}
    },
    {
        "id": "img_008",
        "description": "Vintage car on country road",
        "metadata": {"category": "vehicles", "tags": ["car", "vintage", "road"], "size": "3000x2000"}
    }
]

def generate_image_embedding(description, dimension=512):
    """Simulate generating image embeddings (in real system, use CLIP or similar)"""
    # Create deterministic embedding based on description
    np.random.seed(hash(description) % 2**32)
    embedding = np.random.randn(dimension)
    # Normalize to unit length
    embedding = embedding / np.linalg.norm(embedding)
    return embedding.tolist()

def run_image_search_example():
    """Demonstrates image indexing and similarity search with monitoring"""
    
    print("=" * 60)
    print("Example 2: Image Similarity Search System")
    print("=" * 60)
    
    # Initialize ChromaDB with monitoring
    client = chromadb.HttpClient(host="localhost", port=8000)
    
    # Custom embedding function for images
    class ImageEmbeddingFunction:
        def __call__(self, texts):
            return [generate_image_embedding(text) for text in texts]
    
    # Create monitored wrapper
    db = ChromaDBWrapper(client, ImageEmbeddingFunction())
    
    # 1. Create collection for images
    collection_name = "image_gallery"
    print(f"\n1. Creating collection: {collection_name}")
    
    try:
        client.delete_collection(collection_name)
    except:
        pass
    
    db.create_collection(
        name=collection_name,
        metadata={"description": "Image similarity search system", "embedding_dimension": "512"}
    )
    
    # 2. Index images in batches (simulates bulk upload)
    print("\n2. Indexing images in batches...")
    
    # Batch 1: First 4 images
    print("   Batch 1: Indexing first 4 images")
    batch1_start = time.time()
    result1 = db.add_documents(
        collection_name=collection_name,
        documents=[img["description"] for img in SAMPLE_IMAGES[:4]],
        metadata=[img["metadata"] for img in SAMPLE_IMAGES[:4]],
        ids=[img["id"] for img in SAMPLE_IMAGES[:4]]
    )
    batch1_time = time.time() - batch1_start
    print(f"   Batch 1 completed in {batch1_time:.2f} seconds")
    
    # Batch 2: Next 4 images
    print("   Batch 2: Indexing next 4 images")
    batch2_start = time.time()
    result2 = db.add_documents(
        collection_name=collection_name,
        documents=[img["description"] for img in SAMPLE_IMAGES[4:8]],
        metadata=[img["metadata"] for img in SAMPLE_IMAGES[4:8]],
        ids=[img["id"] for img in SAMPLE_IMAGES[4:8]]
    )
    batch2_time = time.time() - batch2_start
    print(f"   Batch 2 completed in {batch2_time:.2f} seconds")
    
    # 3. Perform similarity searches
    search_queries = [
        ("Find similar pet images", "Cute dog playing outside"),
        ("Find nature scenes", "Beautiful landscape with mountains"),
        ("Find food images", "Fresh organic vegetables"),
        ("Find vacation photos", "Tropical beach paradise"),
        ("Find urban photography", "Modern city architecture")
    ]
    
    print("\n3. Performing image similarity searches...")
    for search_name, query in search_queries:
        print(f"\n   {search_name}")
        print(f"   Query: {query}")
        
        start_time = time.time()
        results = db.search_documents(
            collection_name=collection_name,
            query=query,
            top_k=5
        )
        search_time = time.time() - start_time
        
        print(f"   Search completed in {search_time:.3f} seconds")
        print(f"   Top 3 results:")
        for i, result in enumerate(results[:3], 1):
            print(f"     {i}. {result['document']} (score: {result['score']:.3f})")
            print(f"        Category: {result['metadata']['category']}, Tags: {result['metadata']['tags']}")
    
    # 4. Filter searches by metadata
    print("\n4. Filtered searches by category...")
    
    # Search only in animals category
    print("\n   Searching only in 'animals' category")
    animal_query = "Cute furry friend"
    
    # Note: ChromaDB wrapper would need to be extended for metadata filtering
    # This is a demonstration of the monitoring capability
    start_time = time.time()
    results = db.search_documents(
        collection_name=collection_name,
        query=animal_query,
        top_k=3
    )
    search_time = time.time() - start_time
    
    # Filter results by category (post-processing for demo)
    animal_results = [r for r in results if r['metadata']['category'] == 'animals']
    print(f"   Found {len(animal_results)} animal images in {search_time:.3f} seconds")
    
    # 5. Collection statistics
    print("\n5. Collection Statistics:")
    stats = db.get_collection_stats(collection_name)
    print(f"   {stats}")
    
    print("\n✅ Example 2 complete! Check Grafana for metrics.")
    print("   - Batch insertion performance")
    print("   - Search latency for image queries")
    print("   - Similarity score distribution")
    
    return db, collection_name


if __name__ == "__main__":
    run_image_search_example()
```

## Example 3: Multi-Modal Search System

This example shows monitoring for a system that searches across text, images, and audio.

### Code: `example3_multimodal_search.py`

```python
#!/usr/bin/env python3
"""
Example 3: Multi-Modal Search System
Monitors a system that handles text, image, and audio embeddings
"""

import chromadb
import numpy as np
import time
import sys
sys.path.append('/app')  # For Docker
try:
    from chromadb_wrapper import ChromaDBWrapper
except:
    sys.path.append('.')
    from chromadb_wrapper import ChromaDBWrapper

# Multi-modal content samples
MULTIMODAL_CONTENT = [
    # Text content
    {"id": "text_001", "type": "text", "content": "Introduction to machine learning algorithms", 
     "metadata": {"modality": "text", "language": "en", "length": 42}},
    {"id": "text_002", "type": "text", "content": "Best practices for cloud architecture", 
     "metadata": {"modality": "text", "language": "en", "length": 37}},
    
    # Image descriptions (simulating image embeddings)
    {"id": "img_001", "type": "image", "content": "Diagram showing neural network architecture", 
     "metadata": {"modality": "image", "format": "png", "resolution": "1920x1080"}},
    {"id": "img_002", "type": "image", "content": "Cloud infrastructure diagram with AWS services", 
     "metadata": {"modality": "image", "format": "jpg", "resolution": "2560x1440"}},
    
    # Audio transcriptions (simulating audio embeddings)
    {"id": "audio_001", "type": "audio", "content": "Podcast discussing AI ethics and implications", 
     "metadata": {"modality": "audio", "duration": 1800, "format": "mp3"}},
    {"id": "audio_002", "type": "audio", "content": "Tutorial on setting up Kubernetes cluster", 
     "metadata": {"modality": "audio", "duration": 2400, "format": "wav"}},
]

def generate_multimodal_embedding(content, modality, dimension=768):
    """Generate embeddings based on modality type"""
    # Simulate different embedding models for different modalities
    np.random.seed(hash(f"{content}{modality}") % 2**32)
    
    if modality == "text":
        # Simulate BERT-like embeddings
        embedding = np.random.randn(dimension) * 0.1
    elif modality == "image":
        # Simulate CLIP-like embeddings
        embedding = np.random.randn(dimension) * 0.15
    elif modality == "audio":
        # Simulate wav2vec-like embeddings
        embedding = np.random.randn(dimension) * 0.12
    else:
        embedding = np.random.randn(dimension)
    
    # Normalize
    embedding = embedding / np.linalg.norm(embedding)
    return embedding.tolist()

def run_multimodal_example():
    """Demonstrates multi-modal search with monitoring"""
    
    print("=" * 60)
    print("Example 3: Multi-Modal Search System")
    print("=" * 60)
    
    # Initialize ChromaDB with monitoring
    client = chromadb.HttpClient(host="localhost", port=8000)
    
    # Custom embedding function for multi-modal content
    class MultiModalEmbeddingFunction:
        def __call__(self, texts):
            # In real system, you'd detect modality and use appropriate model
            embeddings = []
            for text in texts:
                # For demo, we'll use the content to determine modality
                if "image" in text.lower() or "diagram" in text.lower():
                    modality = "image"
                elif "audio" in text.lower() or "podcast" in text.lower():
                    modality = "audio"
                else:
                    modality = "text"
                embeddings.append(generate_multimodal_embedding(text, modality))
            return embeddings
    
    # Create monitored wrapper
    db = ChromaDBWrapper(client, MultiModalEmbeddingFunction())
    
    # 1. Create collections for each modality
    print("\n1. Creating multi-modal collections...")
    
    # Unified collection for all modalities
    collection_name = "multimodal_content"
    try:
        client.delete_collection(collection_name)
    except:
        pass
    
    db.create_collection(
        name=collection_name,
        metadata={"description": "Unified multi-modal content", "embedding_dimension": "768"}
    )
    
    # 2. Index content by modality
    print("\n2. Indexing multi-modal content...")
    
    # Group by modality for batch processing
    text_content = [c for c in MULTIMODAL_CONTENT if c["metadata"]["modality"] == "text"]
    image_content = [c for c in MULTIMODAL_CONTENT if c["metadata"]["modality"] == "image"]
    audio_content = [c for c in MULTIMODAL_CONTENT if c["metadata"]["modality"] == "audio"]
    
    # Index text content
    print("   Indexing text content...")
    start_time = time.time()
    db.add_documents(
        collection_name=collection_name,
        documents=[c["content"] for c in text_content],
        metadata=[c["metadata"] for c in text_content],
        ids=[c["id"] for c in text_content]
    )
    text_time = time.time() - start_time
    print(f"   Text indexing completed in {text_time:.2f} seconds")
    
    # Index image content
    print("   Indexing image content...")
    start_time = time.time()
    db.add_documents(
        collection_name=collection_name,
        documents=[c["content"] for c in image_content],
        metadata=[c["metadata"] for c in image_content],
        ids=[c["id"] for c in image_content]
    )
    image_time = time.time() - start_time
    print(f"   Image indexing completed in {image_time:.2f} seconds")
    
    # Index audio content
    print("   Indexing audio content...")
    start_time = time.time()
    db.add_documents(
        collection_name=collection_name,
        documents=[c["content"] for c in audio_content],
        metadata=[c["metadata"] for c in audio_content],
        ids=[c["id"] for c in audio_content]
    )
    audio_time = time.time() - start_time
    print(f"   Audio indexing completed in {audio_time:.2f} seconds")
    
    # 3. Cross-modal searches
    print("\n3. Performing cross-modal searches...")
    
    cross_modal_queries = [
        ("Text query for any content", "How to build scalable systems"),
        ("Image-style query", "Architecture diagram showing microservices"),
        ("Audio-style query", "Tutorial explaining containerization"),
        ("Mixed query", "Visual guide to machine learning concepts")
    ]
    
    for query_type, query in cross_modal_queries:
        print(f"\n   {query_type}: '{query}'")
        
        start_time = time.time()
        results = db.search_documents(
            collection_name=collection_name,
            query=query,
            top_k=6
        )
        search_time = time.time() - start_time
        
        print(f"   Search completed in {search_time:.3f} seconds")
        print(f"   Results across modalities:")
        
        # Group results by modality
        modality_results = {}
        for result in results:
            modality = result['metadata']['modality']
            if modality not in modality_results:
                modality_results[modality] = []
            modality_results[modality].append(result)
        
        for modality, mod_results in modality_results.items():
            print(f"     {modality.upper()}: {len(mod_results)} results")
            if mod_results:
                top_result = mod_results[0]
                print(f"       Top: {top_result['document'][:50]}... (score: {top_result['score']:.3f})")
    
    # 4. Performance comparison across modalities
    print("\n4. Modality-specific search performance...")
    
    modality_queries = {
        "text": "machine learning algorithms",
        "image": "architecture diagram",
        "audio": "technical podcast"
    }
    
    for modality, query in modality_queries.items():
        print(f"\n   Searching in {modality} content only...")
        start_time = time.time()
        
        results = db.search_documents(
            collection_name=collection_name,
            query=query,
            top_k=10
        )
        
        # Filter by modality
        filtered_results = [r for r in results if r['metadata']['modality'] == modality]
        search_time = time.time() - start_time
        
        print(f"   Found {len(filtered_results)} {modality} results in {search_time:.3f} seconds")
        if filtered_results:
            avg_score = sum(r['score'] for r in filtered_results) / len(filtered_results)
            print(f"   Average similarity score: {avg_score:.3f}")
    
    # 5. Collection statistics
    print("\n5. Multi-Modal Collection Statistics:")
    stats = db.get_collection_stats(collection_name)
    print(f"   {stats}")
    
    # Summary by modality
    print("\n   Content by modality:")
    print(f"   - Text: {len(text_content)} items")
    print(f"   - Image: {len(image_content)} items")
    print(f"   - Audio: {len(audio_content)} items")
    
    print("\n✅ Example 3 complete! Check Grafana for metrics.")
    print("   - Modality-specific indexing performance")
    print("   - Cross-modal search effectiveness")
    print("   - Embedding generation times by type")
    
    return db, collection_name


if __name__ == "__main__":
    run_multimodal_example()
```

## Example 4: Production Performance Testing

This example demonstrates how to load test and monitor vector database performance.

### Code: `example4_performance_test.py`

```python
#!/usr/bin/env python3
"""
Example 4: Production Performance Testing
Load tests vector database operations to establish performance baselines
"""

import chromadb
import numpy as np
import time
import concurrent.futures
import statistics
import sys
sys.path.append('/app')  # For Docker
try:
    from chromadb_wrapper import ChromaDBWrapper
except:
    sys.path.append('.')
    from chromadb_wrapper import ChromaDBWrapper

def generate_synthetic_documents(count, doc_length=100):
    """Generate synthetic documents for testing"""
    docs = []
    for i in range(count):
        # Generate realistic-looking technical content
        topics = ["API", "database", "microservice", "container", "cloud", "security", "performance"]
        topic = topics[i % len(topics)]
        doc = f"Document {i}: This is a technical document about {topic} systems. " \
              f"It covers best practices for {topic} implementation and optimization. " \
              f"Key considerations include scalability, reliability, and maintainability."
        docs.append({
            "id": f"doc_{i:06d}",
            "content": doc,
            "metadata": {
                "category": topic,
                "doc_id": i,
                "timestamp": time.time()
            }
        })
    return docs

def run_performance_test():
    """Run comprehensive performance tests with monitoring"""
    
    print("=" * 60)
    print("Example 4: Production Performance Testing")
    print("=" * 60)
    
    # Initialize ChromaDB with monitoring
    client = chromadb.HttpClient(host="localhost", port=8000)
    
    # Use default embedding function for consistency
    from chromadb.utils import embedding_functions
    embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    
    # Create monitored wrapper
    db = ChromaDBWrapper(client, embedding_fn)
    
    # Test configuration
    collection_name = "performance_test"
    
    # Test 1: Bulk insertion performance
    print("\n1. Testing bulk insertion performance...")
    
    try:
        client.delete_collection(collection_name)
    except:
        pass
    
    db.create_collection(collection_name)
    
    # Test different batch sizes
    batch_sizes = [10, 50, 100, 500]
    insertion_times = {}
    
    for batch_size in batch_sizes:
        print(f"\n   Testing batch size: {batch_size}")
        docs = generate_synthetic_documents(batch_size)
        
        start_time = time.time()
        db.add_documents(
            collection_name=collection_name,
            documents=[d["content"] for d in docs],
            metadata=[d["metadata"] for d in docs],
            ids=[d["id"] for d in docs]
        )
        elapsed = time.time() - start_time
        
        insertion_times[batch_size] = elapsed
        docs_per_second = batch_size / elapsed
        print(f"   Inserted {batch_size} documents in {elapsed:.2f} seconds")
        print(f"   Rate: {docs_per_second:.1f} documents/second")
    
    # Test 2: Search performance under load
    print("\n2. Testing search performance...")
    
    # Generate search queries
    search_queries = [
        "best practices for API design",
        "database optimization techniques",
        "microservice architecture patterns",
        "container orchestration strategies",
        "cloud security considerations"
    ]
    
    # Single-threaded search test
    print("\n   Single-threaded search test:")
    search_times = []
    
    for i in range(20):  # 20 searches
        query = search_queries[i % len(search_queries)]
        start_time = time.time()
        results = db.search_documents(
            collection_name=collection_name,
            query=query,
            top_k=10
        )
        elapsed = time.time() - start_time
        search_times.append(elapsed)
    
    avg_search_time = statistics.mean(search_times)
    p95_search_time = sorted(search_times)[int(len(search_times) * 0.95)]
    
    print(f"   Average search time: {avg_search_time:.3f} seconds")
    print(f"   95th percentile: {p95_search_time:.3f} seconds")
    print(f"   Searches per second: {1/avg_search_time:.1f}")
    
    # Test 3: Concurrent operations
    print("\n3. Testing concurrent operations...")
    
    def concurrent_search(query_id):
        """Perform a search operation"""
        query = search_queries[query_id % len(search_queries)]
        start_time = time.time()
        results = db.search_documents(
            collection_name=collection_name,
            query=query,
            top_k=5
        )
        return time.time() - start_time
    
    # Run concurrent searches
    concurrent_levels = [1, 5, 10]
    
    for num_concurrent in concurrent_levels:
        print(f"\n   Testing with {num_concurrent} concurrent searches:")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            start_time = time.time()
            
            # Submit 50 searches
            futures = []
            for i in range(50):
                future = executor.submit(concurrent_search, i)
                futures.append(future)
            
            # Wait for all to complete
            search_times = [f.result() for f in concurrent.futures.as_completed(futures)]
            
            total_time = time.time() - start_time
            
        avg_time = statistics.mean(search_times)
        throughput = len(search_times) / total_time
        
        print(f"   Completed {len(search_times)} searches in {total_time:.2f} seconds")
        print(f"   Average latency: {avg_time:.3f} seconds")
        print(f"   Throughput: {throughput:.1f} searches/second")
    
    # Test 4: Memory efficiency test
    print("\n4. Testing memory efficiency...")
    
    # Add documents in waves to test memory growth
    print("   Adding documents in waves...")
    wave_sizes = [1000, 2000, 5000]
    
    for wave_num, wave_size in enumerate(wave_sizes, 1):
        print(f"\n   Wave {wave_num}: Adding {wave_size} documents")
        docs = generate_synthetic_documents(wave_size, doc_length=50)
        
        # Add with unique IDs
        start_time = time.time()
        db.add_documents(
            collection_name=collection_name,
            documents=[d["content"] for d in docs],
            metadata=[d["metadata"] for d in docs],
            ids=[f"wave{wave_num}_{d['id']}" for d in docs]
        )
        elapsed = time.time() - start_time
        
        print(f"   Added {wave_size} documents in {elapsed:.2f} seconds")
        
        # Get collection stats
        stats = db.get_collection_stats(collection_name)
        print(f"   Collection now has {stats['count']} documents")
    
    # Test 5: Query complexity impact
    print("\n5. Testing query complexity impact...")
    
    complexity_queries = [
        ("Simple", "database"),
        ("Medium", "database optimization performance"),
        ("Complex", "advanced database optimization techniques for high-performance distributed systems"),
        ("Very Complex", "comprehensive guide to database optimization including indexing strategies partitioning techniques and query performance tuning for enterprise scale applications")
    ]
    
    for complexity, query in complexity_queries:
        print(f"\n   {complexity} query: '{query[:50]}...'")
        
        # Run multiple times for average
        times = []
        for _ in range(5):
            start_time = time.time()
            results = db.search_documents(
                collection_name=collection_name,
                query=query,
                top_k=20
            )
            times.append(time.time() - start_time)
        
        avg_time = statistics.mean(times)
        print(f"   Average search time: {avg_time:.3f} seconds")
        print(f"   Top result score: {results[0]['score']:.3f}")
    
    # Final statistics
    print("\n6. Final Performance Summary:")
    final_stats = db.get_collection_stats(collection_name)
    print(f"   Total documents: {final_stats['count']}")
    print(f"   Embedding dimension: {final_stats['dimension']}")
    
    print("\n✅ Example 4 complete! Check Grafana for performance metrics.")
    print("   - Insertion rate by batch size")
    print("   - Search latency distribution")
    print("   - Concurrent operation throughput")
    print("   - Query complexity impact")
    
    return insertion_times, search_times


if __name__ == "__main__":
    run_performance_test()
```

## Running All Examples

Create a script to run all examples sequentially:

### `run_all_examples.sh`

```bash
#!/bin/bash

echo "Running Vector Database Monitoring Examples"
echo "=========================================="

# Ensure ChromaDB is running
echo "Checking ChromaDB..."
if ! curl -s http://localhost:8000/api/v1/heartbeat > /dev/null; then
    echo "Starting ChromaDB..."
    docker compose -f chromadb-compose.yml up -d
    sleep 5
fi

# Ensure vector exporter is in real mode
echo "Configuring vector exporter for real mode..."
docker compose stop vector_db_exporter
DEMO_MODE=false docker compose up -d vector_db_exporter
sleep 5

# Run each example
echo -e "\n\nRunning Example 1: Document RAG System"
docker exec mon_vector_db_exporter python /app/example1_document_rag.py

echo -e "\n\nRunning Example 2: Image Search System"
docker exec mon_vector_db_exporter python /app/example2_image_search.py

echo -e "\n\nRunning Example 3: Multi-Modal Search"
docker exec mon_vector_db_exporter python /app/example3_multimodal_search.py

echo -e "\n\nRunning Example 4: Performance Testing"
docker exec mon_vector_db_exporter python /app/example4_performance_test.py

echo -e "\n\n✅ All examples completed!"
echo "View metrics in Grafana: http://localhost:3000"
echo "Dashboard: Vector Database Monitoring"
```

## Metrics to Observe in Grafana

After running these examples, you'll see:

### 1. **Embedding Generation**
- Different rates for text vs image vs audio embeddings
- Batch size impact on generation time
- Model-specific performance differences

### 2. **Vector Insertions**
- Insertion rates varying by batch size
- Latency distribution for different document types
- Memory usage growth with collection size

### 3. **Similarity Searches**
- Search latency by query complexity
- Similarity score distributions
- Cross-modal search performance

### 4. **System Performance**
- Concurrent operation throughput
- Cache hit rates for repeated queries
- Error rates under load

### 5. **Resource Usage**
- Memory consumption by collection
- Index build times
- Connection pool utilization

## Best Practices Demonstrated

1. **Batch Operations**: Examples show optimal batch sizes for insertion
2. **Query Optimization**: Demonstrates impact of query complexity
3. **Concurrent Access**: Shows how to handle multiple simultaneous operations
4. **Error Handling**: Proper error tracking and recovery
5. **Performance Testing**: Establishing baselines for production

## Extending the Examples

To add your own tests:

1. Copy one of the example files
2. Modify the data and queries for your use case
3. Run with: `docker exec mon_vector_db_exporter python /app/your_example.py`
4. Observe new metrics in Grafana

All examples use the ChromaDBWrapper which automatically tracks:
- Operation counts
- Latency histograms  
- Error rates
- Resource usage

No additional instrumentation needed!
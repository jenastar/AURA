#!/usr/bin/env python3
"""
Generate real vector database activity to produce metrics
"""

import chromadb
import time
import random
import hashlib

def main():
    print("Generating real vector database activity...")
    
    # Connect to ChromaDB
    client = chromadb.HttpClient(host="172.18.0.18", port=8000)
    
    # Create multiple collections
    collections = []
    collection_names = ["documents", "images", "embeddings"]
    
    for name in collection_names:
        try:
            client.delete_collection(name)
        except:
            pass
        
        collection = client.create_collection(name)
        collections.append(collection)
        print(f"Created collection: {name}")
    
    # Generate activity
    for i in range(10):
        print(f"\nIteration {i+1}/10")
        
        for collection in collections:
            # Add documents
            num_docs = random.randint(5, 20)
            docs = [f"Document {j} in {collection.name}" for j in range(num_docs)]
            embeddings = [[random.random() for _ in range(384)] for _ in docs]
            ids = [f"{collection.name}_{i}_{j}" for j in range(num_docs)]
            
            collection.add(
                documents=docs,
                embeddings=embeddings,
                ids=ids
            )
            print(f"  Added {num_docs} docs to {collection.name}")
            
            # Perform searches
            for _ in range(3):
                query_embed = [random.random() for _ in range(384)]
                results = collection.query(
                    query_embeddings=[query_embed],
                    n_results=5
                )
                print(f"  Searched {collection.name}: {len(results['ids'][0])} results")
            
            time.sleep(0.5)
    
    # Final stats
    print("\nFinal collection sizes:")
    for collection in collections:
        count = collection.count()
        print(f"  {collection.name}: {count} documents")
    
    print("\n✅ Activity generation complete!")
    print("Check metrics at http://localhost:9205/metrics")

if __name__ == "__main__":
    main()
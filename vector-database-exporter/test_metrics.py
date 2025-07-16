#!/usr/bin/env python3
"""Test script to verify insertion metrics"""

import time
import uuid
import random
from prometheus_client import start_http_server
from vector_db_metrics_exporter import (
    VectorDatabaseMetricsTracker,
    vector_insertions_total,
    vector_insertion_time
)

def test_insertions():
    # Create tracker
    tracker = VectorDatabaseMetricsTracker("test_db")
    
    print("Starting insertion test...")
    
    # Generate 10 insertion operations
    for i in range(10):
        collection = random.choice(["docs", "images", "audio"])
        batch_size = random.randint(10, 100)
        
        op_id = str(uuid.uuid4())
        print(f"Operation {i+1}: Inserting {batch_size} vectors into {collection}")
        
        tracker.start_operation(op_id, 'vector_insertion', collection, batch_size=batch_size)
        time.sleep(random.uniform(0.01, 0.1))
        tracker.end_operation(op_id, success=True)
    
    # Check metrics
    print("\nChecking metrics...")
    samples = list(vector_insertions_total.collect()[0].samples)
    print(f"Found {len(samples)} insertion metric samples")
    
    for sample in samples:
        if sample.name == 'vector_db_insertions_total':
            print(f"  {sample.labels} -> {sample.value}")
    
    # Also check histogram
    hist_samples = list(vector_insertion_time.collect()[0].samples)
    count_samples = [s for s in hist_samples if s.name == 'vector_db_insertion_seconds_count']
    print(f"\nFound {len(count_samples)} insertion time samples")
    for sample in count_samples:
        print(f"  {sample.labels} -> {sample.value}")

if __name__ == "__main__":
    # Start metrics server
    start_http_server(9206)
    print("Test metrics server started on port 9206")
    
    # Run test
    test_insertions()
    
    print("\nMetrics available at http://localhost:9206/metrics")
    print("Press Ctrl+C to exit")
    
    # Keep running
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nExiting...")
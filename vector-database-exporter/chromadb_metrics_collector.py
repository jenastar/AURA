#!/usr/bin/env python3
"""
ChromaDB Metrics Collector for Production Use
This replaces the demo mode with real ChromaDB monitoring
"""

import os
import time
import chromadb
from vector_db_metrics_exporter import ChromaDBMetricsCollector, start_http_server


def main():
    # Configuration
    port = int(os.environ.get('EXPORTER_PORT', '9205'))
    scrape_interval = int(os.environ.get('SCRAPE_INTERVAL', '10'))
    chroma_host = os.environ.get('CHROMADB_HOST', 'localhost')
    chroma_port = int(os.environ.get('CHROMADB_PORT', '8000')
    
    # Start Prometheus metrics server
    start_http_server(port)
    print(f"ChromaDB Metrics Exporter started on port {port}")
    print(f"Monitoring ChromaDB at {chroma_host}:{chroma_port}")
    
    # Initialize ChromaDB client
    try:
        client = chromadb.HttpClient(
            host=chroma_host,
            port=chroma_port
        )
        print("Successfully connected to ChromaDB")
        
        # Create metrics collector
        collector = ChromaDBMetricsCollector(client)
        
        # Continuous metrics collection
        while True:
            try:
                collector.collect_metrics()
                print(f"Metrics collected at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                print(f"Error collecting metrics: {e}")
            
            time.sleep(scrape_interval)
            
    except Exception as e:
        print(f"Failed to connect to ChromaDB: {e}")
        print("Falling back to demo mode...")
        
        # Fall back to demo mode if ChromaDB is not available
        from vector_db_metrics_exporter import main as demo_main
        demo_main()


if __name__ == "__main__":
    main()
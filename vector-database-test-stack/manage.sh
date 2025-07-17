#!/bin/bash

# Vector Database Test Stack Management Script

set -e

COMMAND=${1:-help}

case $COMMAND in
  start)
    echo "Starting Vector Database Test Stack..."
    docker compose up -d
    echo "Waiting for ChromaDB to be ready..."
    sleep 5
    if curl -s http://localhost:8001/api/v1/heartbeat | grep -q 'heartbeat'; then
      echo "✅ ChromaDB is ready at http://localhost:8001"
    else
      echo "⚠️  ChromaDB may not be ready yet"
    fi
    docker compose ps
    ;;
    
  stop)
    echo "Stopping Vector Database Test Stack..."
    docker compose down
    ;;
    
  restart)
    echo "Restarting Vector Database Test Stack..."
    docker compose restart
    ;;
    
  logs)
    docker compose logs -f ${2:-}
    ;;
    
  status)
    echo "Vector Database Test Stack Status:"
    docker compose ps
    echo ""
    echo "ChromaDB Collections:"
    curl -s http://localhost:8001/api/v1/collections 2>/dev/null | python3 -m json.tool || echo "ChromaDB not accessible"
    ;;
    
  clean)
    echo "⚠️  This will remove all data. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
      docker compose down -v
      echo "✅ Cleaned up all containers and volumes"
    else
      echo "Cancelled"
    fi
    ;;
    
  connect-monitoring)
    echo "Connecting test stack to main monitoring network..."
    docker network connect aura_mon_network test_chromadb 2>/dev/null || echo "Already connected or network doesn't exist"
    echo "✅ Connected. The main monitoring stack can now access test_chromadb:8000"
    ;;
    
  demo)
    echo "Starting demo with RAG application..."
    docker compose --profile rag up -d
    echo "✅ Demo stack started with RAG test application"
    ;;
    
  help|*)
    echo "Vector Database Test Stack Manager"
    echo ""
    echo "Usage: ./manage.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start              - Start the test stack"
    echo "  stop               - Stop the test stack"
    echo "  restart            - Restart all services"
    echo "  logs [service]     - View logs (all services or specific one)"
    echo "  status             - Show status and collections"
    echo "  clean              - Remove all containers and data"
    echo "  connect-monitoring - Connect to main monitoring network"
    echo "  demo               - Start with RAG demo application"
    echo "  help               - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./manage.sh start"
    echo "  ./manage.sh logs chromadb"
    echo "  ./manage.sh status"
    ;;
esac
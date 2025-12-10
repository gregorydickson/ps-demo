#!/bin/bash
set -e

echo "Running local production test with Docker Compose..."

# Check for required env vars
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "Error: GOOGLE_API_KEY environment variable not set"
    echo "Export it or create a .env file"
    exit 1
fi

if [ -z "$LLAMA_CLOUD_API_KEY" ]; then
    echo "Error: LLAMA_CLOUD_API_KEY environment variable not set"
    echo "Export it or create a .env file"
    exit 1
fi

# Build images
echo ""
echo "=== Building Images ==="
docker-compose -f docker-compose.prod.yml build

# Start services
echo ""
echo "=== Starting Services ==="
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be healthy
echo ""
echo "=== Waiting for Services ==="
echo "Waiting for backend health check..."

for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null; then
        echo "Backend is healthy!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

echo "Waiting for frontend..."
for i in {1..30}; do
    if curl -s http://localhost:3000 > /dev/null; then
        echo "Frontend is healthy!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Show status
echo ""
echo "=== Service Status ==="
docker-compose -f docker-compose.prod.yml ps

echo ""
echo "=== URLs ==="
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "Backend Docs: http://localhost:8000/docs"

echo ""
echo "=== Logs ==="
echo "To view logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "To stop: docker-compose -f docker-compose.prod.yml down"

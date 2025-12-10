#!/bin/bash
set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
TAG="${1:-latest}"

echo "Building and pushing images for project: $PROJECT_ID"
echo "Tag: $TAG"

# Configure Docker for GCR
echo "Configuring Docker for GCR..."
gcloud auth configure-docker gcr.io --quiet

# Build and push backend
echo ""
echo "=== Building Backend ==="
docker build \
    -t "gcr.io/${PROJECT_ID}/contract-intelligence-backend:${TAG}" \
    -f backend/Dockerfile \
    backend/

echo "Pushing backend image..."
docker push "gcr.io/${PROJECT_ID}/contract-intelligence-backend:${TAG}"

# Build and push frontend
echo ""
echo "=== Building Frontend ==="
docker build \
    -t "gcr.io/${PROJECT_ID}/contract-intelligence-frontend:${TAG}" \
    -f frontend/Dockerfile \
    frontend/

echo "Pushing frontend image..."
docker push "gcr.io/${PROJECT_ID}/contract-intelligence-frontend:${TAG}"

echo ""
echo "=== Build Complete ==="
echo "Backend: gcr.io/${PROJECT_ID}/contract-intelligence-backend:${TAG}"
echo "Frontend: gcr.io/${PROJECT_ID}/contract-intelligence-frontend:${TAG}"

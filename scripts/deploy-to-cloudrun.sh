#!/bin/bash
set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
TAG="${1:-latest}"

# Infrastructure URLs (update after deploying databases)
REDIS_HOST="${REDIS_HOST:-10.0.0.1}"
FALKORDB_HOST="${FALKORDB_HOST:-10.0.0.2}"

echo "Deploying to Cloud Run in project: $PROJECT_ID"
echo "Region: $REGION"
echo "Tag: $TAG"

# Deploy backend
echo ""
echo "=== Deploying Backend ==="
gcloud run deploy contract-intelligence-backend \
    --image "gcr.io/${PROJECT_ID}/contract-intelligence-backend:${TAG}" \
    --platform managed \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --allow-unauthenticated \
    --service-account "contract-intelligence-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-secrets "GOOGLE_API_KEY=google-api-key:latest,LLAMA_CLOUD_API_KEY=llama-cloud-api-key:latest" \
    --set-env-vars "REDIS_URL=redis://${REDIS_HOST}:6380,FALKORDB_URL=redis://${FALKORDB_HOST}:6379,LOG_LEVEL=INFO,LOG_FORMAT=json" \
    --memory "2Gi" \
    --cpu "2" \
    --timeout "300" \
    --min-instances "0" \
    --max-instances "10"

# Get backend URL
BACKEND_URL=$(gcloud run services describe contract-intelligence-backend \
    --platform managed \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --format "value(status.url)")

echo "Backend deployed at: $BACKEND_URL"

# Deploy frontend
echo ""
echo "=== Deploying Frontend ==="
gcloud run deploy contract-intelligence-frontend \
    --image "gcr.io/${PROJECT_ID}/contract-intelligence-frontend:${TAG}" \
    --platform managed \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --allow-unauthenticated \
    --set-env-vars "NEXT_PUBLIC_API_URL=${BACKEND_URL}" \
    --memory "512Mi" \
    --cpu "1" \
    --timeout "60" \
    --min-instances "0" \
    --max-instances "5"

# Get frontend URL
FRONTEND_URL=$(gcloud run services describe contract-intelligence-frontend \
    --platform managed \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --format "value(status.url)")

echo ""
echo "=== Deployment Complete ==="
echo "Frontend: $FRONTEND_URL"
echo "Backend API: $BACKEND_URL"
echo "Backend Docs: ${BACKEND_URL}/docs"

# Deployment Guide - Legal Contract Intelligence Platform

## Overview

This guide covers deploying the Legal Contract Intelligence Platform to Google Cloud Platform using Cloud Run.

## Prerequisites

- GCP project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed locally
- API keys for Google AI and LlamaParse

## Quick Start

### 1. Configure Environment

```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export GOOGLE_API_KEY="your-google-api-key"
export LLAMA_CLOUD_API_KEY="your-llamaparse-key"
```

### 2. Set Up GCP Secrets (One-time setup)

```bash
./gcp/setup-secrets.sh
```

This script will:
- Enable required GCP APIs (Secret Manager, Cloud Run, Container Registry)
- Create secrets for API keys
- Create a service account with appropriate permissions
- Grant secret access to the service account

### 3. Local Production Test (Optional)

Before deploying to GCP, test the production build locally:

```bash
./scripts/local-prod-test.sh
```

This will:
- Build production Docker images
- Start all services with docker-compose
- Wait for health checks
- Display service URLs

Access the local deployment:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 4. Build and Push Images to GCR

```bash
./scripts/build-and-push.sh v1.0.0
```

This builds both backend and frontend images and pushes them to Google Container Registry.

### 5. Deploy to Cloud Run

```bash
# Note: Set REDIS_HOST and FALKORDB_HOST before running
export REDIS_HOST="your-redis-ip"
export FALKORDB_HOST="your-falkordb-ip"

./scripts/deploy-to-cloudrun.sh v1.0.0
```

The script will:
- Deploy the backend service with secrets and environment variables
- Deploy the frontend service configured to use the backend
- Display the URLs for both services

## Architecture

### Container Images

#### Backend
- **Base Image**: python:3.11-slim
- **Build Type**: Multi-stage
- **Final Size**: < 500MB
- **Security**: Non-root user (appuser)
- **Health Check**: `/health` endpoint

#### Frontend
- **Base Image**: node:20-alpine
- **Build Type**: Multi-stage with standalone output
- **Final Size**: < 200MB
- **Security**: Non-root user (nextjs)
- **Health Check**: Root path `/`

### Cloud Run Configuration

#### Backend Service
- **CPU**: 2 cores
- **Memory**: 2Gi
- **Timeout**: 300s
- **Scaling**: 0-10 instances
- **Secrets**: Google API Key, LlamaParse API Key (from Secret Manager)
- **Environment**: REDIS_URL, FALKORDB_URL, LOG_LEVEL, LOG_FORMAT

#### Frontend Service
- **CPU**: 1 core
- **Memory**: 512Mi
- **Timeout**: 60s
- **Scaling**: 0-5 instances
- **Environment**: NEXT_PUBLIC_API_URL (backend URL)

## Database Setup

### Option 1: Cloud Memorystore (Recommended for Production)

```bash
# Create Redis instance for caching
gcloud redis instances create contract-intel-cache \
    --size=1 \
    --region=$GCP_REGION \
    --redis-version=redis_7_0

# Create second Redis instance for FalkorDB (or use Compute Engine)
gcloud redis instances create contract-intel-graph \
    --size=1 \
    --region=$GCP_REGION \
    --redis-version=redis_7_0
```

### Option 2: Compute Engine

Deploy Redis and FalkorDB on Compute Engine VMs with persistent disks.

## File Structure

```
.
├── backend/
│   ├── Dockerfile              # Multi-stage Python backend
│   └── .dockerignore          # Exclude dev files
├── frontend/
│   ├── Dockerfile              # Multi-stage Next.js frontend
│   ├── .dockerignore          # Exclude dev files
│   └── next.config.js         # Standalone output config
├── gcp/
│   ├── cloudrun-backend.yaml  # Backend Cloud Run config
│   ├── cloudrun-frontend.yaml # Frontend Cloud Run config
│   └── setup-secrets.sh       # Secret Manager setup
├── scripts/
│   ├── build-and-push.sh      # Build & push to GCR
│   ├── deploy-to-cloudrun.sh  # Deploy to Cloud Run
│   └── local-prod-test.sh     # Test locally
└── docker-compose.prod.yml    # Local production testing
```

## Deployment Workflow

### Development → Production

1. **Develop locally** using `docker-compose.yml`
2. **Test production build** with `./scripts/local-prod-test.sh`
3. **Build images** with `./scripts/build-and-push.sh <version>`
4. **Deploy** with `./scripts/deploy-to-cloudrun.sh <version>`

### Continuous Deployment (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      - name: Build and Push
        run: |
          export GCP_PROJECT_ID=${{ secrets.GCP_PROJECT_ID }}
          ./scripts/build-and-push.sh ${{ github.sha }}
      - name: Deploy
        run: |
          export GCP_PROJECT_ID=${{ secrets.GCP_PROJECT_ID }}
          export REDIS_HOST=${{ secrets.REDIS_HOST }}
          export FALKORDB_HOST=${{ secrets.FALKORDB_HOST }}
          ./scripts/deploy-to-cloudrun.sh ${{ github.sha }}
```

## Monitoring & Observability

### Cloud Run Metrics

View metrics in the GCP Console:
- Request count and latency
- Container instance count
- CPU and memory utilization
- Error rates

### Logs

```bash
# Backend logs
gcloud run services logs read contract-intelligence-backend \
    --region=$GCP_REGION \
    --project=$GCP_PROJECT_ID

# Frontend logs
gcloud run services logs read contract-intelligence-frontend \
    --region=$GCP_REGION \
    --project=$GCP_PROJECT_ID
```

### Structured Logging

Backend logs are in JSON format with fields:
- `timestamp`: ISO 8601 timestamp
- `level`: Log level (INFO, WARNING, ERROR)
- `message`: Log message
- `request_id`: Request correlation ID

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Backend cold start | < 30s | Multi-stage build optimization |
| Frontend cold start | < 10s | Standalone Next.js output |
| Backend p50 latency | < 500ms | Excluding LLM processing |
| Backend p99 latency | < 2s | Excluding LLM processing |
| Container size (backend) | < 500MB | Multi-stage build |
| Container size (frontend) | < 200MB | Alpine-based image |

## Cost Optimization

### Cloud Run Pricing Factors
- CPU/Memory allocation
- Request count
- Cold start frequency
- Minimum instances

### Recommendations
1. Set `minScale: 0` for development (already configured)
2. Consider `minScale: 1` for production to avoid cold starts
3. Monitor and adjust CPU/memory based on actual usage
4. Use Cloud Memorystore for Redis in production (better than Cloud Run scaling)

## Security

### Container Security
- Non-root users in all containers
- Multi-stage builds (no build tools in final image)
- Minimal base images (slim/alpine)
- No secrets in images (use Secret Manager)

### Network Security
- All traffic over HTTPS (Cloud Run default)
- Service-to-service authentication possible via IAM
- VPC connector for private database access

### Secret Management
- API keys stored in Secret Manager
- Service account with least-privilege access
- Secrets mounted as environment variables at runtime

## Troubleshooting

### Build Failures

```bash
# Test backend build locally
docker build -f backend/Dockerfile backend/

# Test frontend build locally
docker build -f frontend/Dockerfile frontend/
```

### Deployment Failures

```bash
# Check Cloud Run service status
gcloud run services describe contract-intelligence-backend \
    --region=$GCP_REGION \
    --project=$GCP_PROJECT_ID

# Check recent revisions
gcloud run revisions list \
    --service=contract-intelligence-backend \
    --region=$GCP_REGION \
    --project=$GCP_PROJECT_ID
```

### Runtime Issues

```bash
# View live logs
gcloud run services logs tail contract-intelligence-backend \
    --region=$GCP_REGION \
    --project=$GCP_PROJECT_ID

# Check service health
curl https://contract-intelligence-backend-<region>-<project>.a.run.app/health
```

## Rollback

```bash
# List revisions
gcloud run revisions list \
    --service=contract-intelligence-backend \
    --region=$GCP_REGION

# Rollback to previous revision
gcloud run services update-traffic contract-intelligence-backend \
    --to-revisions=<previous-revision>=100 \
    --region=$GCP_REGION
```

## Next Steps

1. Set up Cloud Monitoring alerts
2. Configure Cloud Trace for distributed tracing
3. Set up Cloud Armor for DDoS protection
4. Implement CI/CD pipeline
5. Configure custom domain with Cloud Load Balancing
6. Set up Cloud CDN for static assets

## Support

For issues or questions:
- Check logs first
- Review GCP documentation
- Consult the main README.md for application details

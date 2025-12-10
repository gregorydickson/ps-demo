# Part 7: GCP Deployment Preparation

## 🔴 STATUS: NOT STARTED

**Priority:** HIGH (Required for Demo)
**Parallel Execution:** Can run in parallel with Parts 5 & 6
**Dependencies:** Parts 1-4 complete
**Estimated Effort:** 3-4 hours

---

## Overview

This part prepares the application for deployment to Google Cloud Platform:
- Dockerize backend and frontend
- Configure for Cloud Run deployment
- Set up Secret Manager for API keys
- Create deployment scripts

---

## Parallel Task Groups

### Group 7A: Containerization (Backend + Frontend Dockerfiles)
### Group 7B: GCP Configuration (Cloud Run + Secret Manager)
### Group 7C: Deployment Scripts (CI/CD ready)

---

## Group 7A: Containerization

**Files to Create:**
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `docker-compose.prod.yml`

### Task 7A.1: Backend Dockerfile

**File:** `backend/Dockerfile`

```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY . .

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**File:** `backend/.dockerignore`

```
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
venv
.venv
pip-log.txt
pip-delete-this-directory.txt
.tox
.coverage
.coverage.*
htmlcov
.pytest_cache
.mypy_cache
.ruff_cache
*.egg-info
.installed.cfg
*.egg
.env
.env.*
*.log
tests/
docs/
*.md
!README.md
```

### Success Criteria
- [ ] Multi-stage build for small image size
- [ ] Non-root user for security
- [ ] Health check configured
- [ ] .dockerignore excludes test files

---

### Task 7A.2: Frontend Dockerfile

**File:** `frontend/Dockerfile`

```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Production stage
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
```

**Update `frontend/next.config.js`:**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',  // Required for Docker deployment

  // Environment variables available at runtime
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
}

module.exports = nextConfig
```

**File:** `frontend/.dockerignore`

```
node_modules
.next
.git
*.md
!README.md
.env*
.eslintrc*
.prettierrc*
jest.config.*
vitest.config.*
__tests__
coverage
```

### Success Criteria
- [ ] Standalone output configured
- [ ] Multi-stage build
- [ ] Non-root user
- [ ] Image size < 200MB

---

### Task 7A.3: Production Docker Compose

**File:** `docker-compose.prod.yml`

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - LLAMA_CLOUD_API_KEY=${LLAMA_CLOUD_API_KEY}
      - REDIS_URL=redis://redis:6380
      - FALKORDB_URL=redis://falkordb:6379
      - LOG_LEVEL=INFO
      - LOG_FORMAT=json
    depends_on:
      falkordb:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend
    restart: unless-stopped

  falkordb:
    image: falkordb/falkordb:latest
    ports:
      - "6379:6379"
    volumes:
      - falkordb_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --port 6380
    ports:
      - "6380:6380"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-p", "6380", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  falkordb_data:
  redis_data:
```

### Success Criteria
- [ ] All services defined
- [ ] Health checks configured
- [ ] Persistent volumes for databases
- [ ] Proper dependency ordering

---

## Group 7B: GCP Configuration

**Files to Create:**
- `gcp/cloudrun-backend.yaml`
- `gcp/cloudrun-frontend.yaml`
- `gcp/setup-secrets.sh`

### Task 7B.1: Cloud Run Backend Configuration

**File:** `gcp/cloudrun-backend.yaml`

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: contract-intelligence-backend
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"
        autoscaling.knative.dev/maxScale: "10"
        run.googleapis.com/cpu-throttling: "false"
    spec:
      containerConcurrency: 80
      timeoutSeconds: 300
      serviceAccountName: contract-intelligence-sa@${PROJECT_ID}.iam.gserviceaccount.com
      containers:
        - image: gcr.io/${PROJECT_ID}/contract-intelligence-backend:latest
          ports:
            - containerPort: 8000
          resources:
            limits:
              cpu: "2"
              memory: "2Gi"
          env:
            - name: GOOGLE_API_KEY
              valueFrom:
                secretKeyRef:
                  name: google-api-key
                  key: latest
            - name: LLAMA_CLOUD_API_KEY
              valueFrom:
                secretKeyRef:
                  name: llama-cloud-api-key
                  key: latest
            - name: REDIS_URL
              value: "redis://${REDIS_HOST}:6380"
            - name: FALKORDB_URL
              value: "redis://${FALKORDB_HOST}:6379"
            - name: LOG_LEVEL
              value: "INFO"
            - name: LOG_FORMAT
              value: "json"
          startupProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            periodSeconds: 30
```

### Success Criteria
- [ ] CPU/memory limits configured
- [ ] Secrets from Secret Manager
- [ ] Health probes configured
- [ ] Auto-scaling configured

---

### Task 7B.2: Cloud Run Frontend Configuration

**File:** `gcp/cloudrun-frontend.yaml`

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: contract-intelligence-frontend
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"
        autoscaling.knative.dev/maxScale: "5"
    spec:
      containerConcurrency: 100
      timeoutSeconds: 60
      containers:
        - image: gcr.io/${PROJECT_ID}/contract-intelligence-frontend:latest
          ports:
            - containerPort: 3000
          resources:
            limits:
              cpu: "1"
              memory: "512Mi"
          env:
            - name: NEXT_PUBLIC_API_URL
              value: "https://contract-intelligence-backend-${REGION}-${PROJECT_ID}.a.run.app"
          startupProbe:
            httpGet:
              path: /
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 3
```

### Success Criteria
- [ ] Points to backend Cloud Run URL
- [ ] Lower resource limits (static serving)
- [ ] Faster startup than backend

---

### Task 7B.3: Secret Manager Setup Script

**File:** `gcp/setup-secrets.sh`

```bash
#!/bin/bash
set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"

echo "Setting up GCP secrets for project: $PROJECT_ID"

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable \
    secretmanager.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    --project="$PROJECT_ID"

# Create secrets (if they don't exist)
echo "Creating secrets..."

# Google API Key
if ! gcloud secrets describe google-api-key --project="$PROJECT_ID" &>/dev/null; then
    echo "Creating google-api-key secret..."
    echo -n "Enter your Google API Key: "
    read -s GOOGLE_API_KEY
    echo
    echo -n "$GOOGLE_API_KEY" | gcloud secrets create google-api-key \
        --data-file=- \
        --project="$PROJECT_ID" \
        --replication-policy="automatic"
else
    echo "google-api-key already exists"
fi

# LlamaParse API Key
if ! gcloud secrets describe llama-cloud-api-key --project="$PROJECT_ID" &>/dev/null; then
    echo "Creating llama-cloud-api-key secret..."
    echo -n "Enter your LlamaParse API Key: "
    read -s LLAMA_CLOUD_API_KEY
    echo
    echo -n "$LLAMA_CLOUD_API_KEY" | gcloud secrets create llama-cloud-api-key \
        --data-file=- \
        --project="$PROJECT_ID" \
        --replication-policy="automatic"
else
    echo "llama-cloud-api-key already exists"
fi

# Create service account for Cloud Run
SA_NAME="contract-intelligence-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
    echo "Creating service account..."
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name="Contract Intelligence Service Account" \
        --project="$PROJECT_ID"
fi

# Grant secret access to service account
echo "Granting secret access..."
for SECRET in google-api-key llama-cloud-api-key; do
    gcloud secrets add-iam-policy-binding "$SECRET" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID"
done

echo "Secret setup complete!"
echo ""
echo "Next steps:"
echo "1. Deploy FalkorDB and Redis (consider Cloud Memorystore or Compute Engine)"
echo "2. Build and push Docker images"
echo "3. Deploy to Cloud Run"
```

### Success Criteria
- [ ] Creates required secrets
- [ ] Creates service account
- [ ] Grants appropriate permissions
- [ ] Idempotent (can run multiple times)

---

## Group 7C: Deployment Scripts

**Files to Create:**
- `scripts/build-and-push.sh`
- `scripts/deploy-to-cloudrun.sh`
- `scripts/local-prod-test.sh`

### Task 7C.1: Build and Push Script

**File:** `scripts/build-and-push.sh`

```bash
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
```

### Success Criteria
- [ ] Builds both images
- [ ] Pushes to GCR
- [ ] Supports custom tags
- [ ] Shows progress

---

### Task 7C.2: Deploy to Cloud Run Script

**File:** `scripts/deploy-to-cloudrun.sh`

```bash
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
```

### Success Criteria
- [ ] Deploys both services
- [ ] Configures secrets
- [ ] Sets environment variables
- [ ] Outputs URLs

---

### Task 7C.3: Local Production Test Script

**File:** `scripts/local-prod-test.sh`

```bash
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
```

### Success Criteria
- [ ] Validates environment variables
- [ ] Builds and starts all services
- [ ] Waits for health checks
- [ ] Shows helpful URLs and commands

---

## Completion Checklist

### Group 7A: Containerization
- [ ] Task 7A.1: Backend Dockerfile
- [ ] Task 7A.2: Frontend Dockerfile
- [ ] Task 7A.3: Production Docker Compose

### Group 7B: GCP Configuration
- [ ] Task 7B.1: Cloud Run backend config
- [ ] Task 7B.2: Cloud Run frontend config
- [ ] Task 7B.3: Secret Manager setup script

### Group 7C: Deployment Scripts
- [ ] Task 7C.1: Build and push script
- [ ] Task 7C.2: Deploy to Cloud Run script
- [ ] Task 7C.3: Local production test script

---

## Quick Deployment Guide

```bash
# 1. Set up secrets (one time)
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
./gcp/setup-secrets.sh

# 2. Build and push images
./scripts/build-and-push.sh v1.0.0

# 3. Deploy to Cloud Run
./scripts/deploy-to-cloudrun.sh v1.0.0

# 4. (Optional) Test locally first
export GOOGLE_API_KEY="your-key"
export LLAMA_CLOUD_API_KEY="your-key"
./scripts/local-prod-test.sh
```

---

## Prerequisites

- GCP project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed
- FalkorDB and Redis deployed (Compute Engine or Memorystore)

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Backend container size | < 500MB |
| Frontend container size | < 200MB |
| Cold start time (backend) | < 30s |
| Cold start time (frontend) | < 10s |
| Deployment time | < 5 minutes |

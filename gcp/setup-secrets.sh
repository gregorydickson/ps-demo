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

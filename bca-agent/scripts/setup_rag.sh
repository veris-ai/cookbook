#!/bin/bash
# Setup Vertex AI RAG corpus and upload the procedure document.
# Usage: ./scripts/setup_rag.sh
#
# Prerequisites:
#   - gcloud CLI authenticated (gcloud auth login)
#   - GCP project set (gcloud config set project <project-id>)
#   - Vertex AI API enabled

set -euo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
LOCATION="europe-west4"
BUCKET_NAME="${PROJECT_ID}-bca-rag"
DOC_PATH="docs/clear_cuid_procedure.md"
CORPUS_DISPLAY_NAME="bca-clear-cuid-procedures"

echo "=== BCA RAG Corpus Setup ==="
echo "Project:  $PROJECT_ID"
echo "Location: $LOCATION"
echo "Bucket:   gs://$BUCKET_NAME"
echo ""

# 1. Enable Vertex AI API (idempotent)
echo "1. Enabling Vertex AI API..."
gcloud services enable aiplatform.googleapis.com --quiet

# 2. Create GCS bucket if it doesn't exist
echo "2. Creating GCS bucket..."
gcloud storage buckets create "gs://$BUCKET_NAME" \
  --location="$LOCATION" \
  --quiet 2>/dev/null || echo "   Bucket already exists."

# 3. Upload procedure document to GCS
echo "3. Uploading procedure document to GCS..."
gcloud storage cp "$DOC_PATH" "gs://$BUCKET_NAME/clear_cuid_procedure.md"

# 4. Check if corpus already exists
echo "4. Checking for existing RAG corpus..."
EXISTING=$(curl -s \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://${LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_ID}/locations/${LOCATION}/ragCorpora")

CORPUS_NAME=$(echo "$EXISTING" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for c in data.get('ragCorpora', []):
    if c.get('displayName') == '$CORPUS_DISPLAY_NAME':
        print(c['name'])
        break
" 2>/dev/null || echo "")

if [[ -n "$CORPUS_NAME" ]]; then
  echo "   Found existing corpus: $CORPUS_NAME"
else
  echo "   Creating new RAG corpus..."
  CORPUS_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "Content-Type: application/json" \
    -d "{
      \"display_name\": \"$CORPUS_DISPLAY_NAME\",
      \"description\": \"Clear CUID procedure document for Banker Connections Agent POC\"
    }" \
    "https://${LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_ID}/locations/${LOCATION}/ragCorpora")

  OPERATION_NAME=$(echo "$CORPUS_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name',''))" 2>/dev/null || echo "")

  if [[ "$OPERATION_NAME" == *"operations"* ]]; then
    echo "   Waiting for corpus creation (polling every 10s)..."
    for i in $(seq 1 12); do
      sleep 10
      OP_RESULT=$(curl -s \
        -H "Authorization: Bearer $(gcloud auth print-access-token)" \
        "https://${LOCATION}-aiplatform.googleapis.com/v1beta1/${OPERATION_NAME}")

      DONE=$(echo "$OP_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('done', False))" 2>/dev/null || echo "False")

      if [[ "$DONE" == "True" ]]; then
        CORPUS_NAME=$(echo "$OP_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['response']['name'])" 2>/dev/null || echo "")
        echo "   Corpus created: $CORPUS_NAME"
        break
      fi
      echo "   Still waiting... (${i}0s)"
    done
  fi
fi

if [[ -z "$CORPUS_NAME" ]]; then
  echo "   ERROR: Could not create or find corpus."
  exit 1
fi

# Extract corpus ID
CORPUS_ID=$(echo "$CORPUS_NAME" | sed -n 's/.*ragCorpora\/\([0-9]*\).*/\1/p')
echo "   Corpus ID: $CORPUS_ID"

# 5. Import the document into the RAG corpus
echo "5. Importing document into RAG corpus..."
IMPORT_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d "{
    \"importRagFilesConfig\": {
      \"gcsSource\": {
        \"uris\": [\"gs://${BUCKET_NAME}/clear_cuid_procedure.md\"]
      },
      \"ragFileChunkingConfig\": {
        \"chunkSize\": 512,
        \"chunkOverlap\": 100
      }
    }
  }" \
  "https://${LOCATION}-aiplatform.googleapis.com/v1beta1/projects/${PROJECT_ID}/locations/${LOCATION}/ragCorpora/${CORPUS_ID}/ragFiles:import")

echo "   Import response: $IMPORT_RESPONSE"

# 6. Print env vars to set
echo ""
echo "=== Done! Add these to your .env ==="
echo "GCP_PROJECT=$PROJECT_ID"
echo "GCP_LOCATION=$LOCATION"
echo "RAG_CORPUS_ID=$CORPUS_ID"

#!/bin/bash
# Deploys the MAF workflow as an Azure Machine Learning Managed Online Endpoint
# using the standard scoring-script pattern (init/run).
#
# Replaces: Prompt Flow Managed Online Endpoint.
#
# Prerequisites:
#   - az login completed
#   - Azure ML workspace already exists
#   - The ml CLI extension is installed: az extension add -n ml
#   - envsubst is available (part of gettext)
#   - For keyless auth to Foundry, assign a managed identity with the
#     appropriate role — see managed_identity.md for details.
#
# Required environment variables:
#   SUBSCRIPTION_ID                  - Azure subscription ID
#   RESOURCE_GROUP                   - Resource group containing the AML workspace
#   WORKSPACE_NAME                   - Azure ML workspace name
#   FOUNDRY_PROJECT_ENDPOINT         - Foundry project endpoint URL
#   FOUNDRY_MODEL                    - Model name (e.g. gpt-4o)
#
# Optional environment variables:
#   MAF_WORKFLOW_FILE                - Workflow file path (default: phase-2-rebuild/01_linear_flow.py)
#   INSTANCE_TYPE                    - VM SKU (default: Standard_DS3_v2)
#   INSTANCE_COUNT                   - Number of instances (default: 1)
#   AZURE_AI_SEARCH_ENDPOINT         - AI Search endpoint (for RAG workflows)
#   AZURE_AI_SEARCH_INDEX_NAME       - AI Search index name
#   AZURE_AI_SEARCH_API_KEY          - AI Search API key
#   APPLICATIONINSIGHTS_CONNECTION_STRING - App Insights connection string (enables tracing)
#
# Usage: bash deploy.sh

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
GUIDE_DIR=$(cd "${SCRIPT_DIR}/../.." && pwd)
cd "$GUIDE_DIR"

SUBSCRIPTION_ID="${SUBSCRIPTION_ID:?Set SUBSCRIPTION_ID}"
RESOURCE_GROUP="${RESOURCE_GROUP:?Set RESOURCE_GROUP}"
WORKSPACE_NAME="${WORKSPACE_NAME:?Set WORKSPACE_NAME}"

# ── Export variables that deployment.yml references via envsubst ──────
export FOUNDRY_PROJECT_ENDPOINT="${FOUNDRY_PROJECT_ENDPOINT:?Set FOUNDRY_PROJECT_ENDPOINT}"
export FOUNDRY_MODEL="${FOUNDRY_MODEL:?Set FOUNDRY_MODEL}"
export MAF_WORKFLOW_FILE="${MAF_WORKFLOW_FILE:-phase-2-rebuild/01_linear_flow.py}"
export INSTANCE_TYPE="${INSTANCE_TYPE:-Standard_DS3_v2}"
export INSTANCE_COUNT="${INSTANCE_COUNT:-1}"
export AZURE_AI_SEARCH_ENDPOINT="${AZURE_AI_SEARCH_ENDPOINT:-}"
export AZURE_AI_SEARCH_INDEX_NAME="${AZURE_AI_SEARCH_INDEX_NAME:-}"
export AZURE_AI_SEARCH_API_KEY="${AZURE_AI_SEARCH_API_KEY:-}"
export APPLICATIONINSIGHTS_CONNECTION_STRING="${APPLICATIONINSIGHTS_CONNECTION_STRING:-}"

# ── Render deployment YAML with current environment variables ────────
RENDERED_DEPLOYMENT=$(mktemp --suffix=.yml)
SUBST_VARS='${FOUNDRY_PROJECT_ENDPOINT} ${FOUNDRY_MODEL} ${MAF_WORKFLOW_FILE} ${INSTANCE_TYPE} ${INSTANCE_COUNT} ${AZURE_AI_SEARCH_ENDPOINT} ${AZURE_AI_SEARCH_INDEX_NAME} ${AZURE_AI_SEARCH_API_KEY} ${APPLICATIONINSIGHTS_CONNECTION_STRING}'
envsubst "$SUBST_VARS" < "${SCRIPT_DIR}/deployment.yml" > "$RENDERED_DEPLOYMENT"

# ── Create managed online endpoint ──────────────────────────────────
echo "Creating online endpoint..."
az ml online-endpoint create \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --file "${SCRIPT_DIR}/endpoint.yml" \
  2>/dev/null || echo "Endpoint already exists, continuing..."

# ── Create deployment under the endpoint ─────────────────────────────
echo "Creating deployment..."
az ml online-deployment create \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --file "$RENDERED_DEPLOYMENT" \
  --all-traffic

rm -f "$RENDERED_DEPLOYMENT"

# ── Smoke test ───────────────────────────────────────────────────────
ENDPOINT_NAME=$(grep '^name:' "${SCRIPT_DIR}/endpoint.yml" | awk '{print $2}')

echo "Running smoke test..."
az ml online-endpoint invoke \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --name "$ENDPOINT_NAME" \
  --request-file <(echo '{"question": "What is the refund policy?"}')

echo ""
echo "Endpoint deployed successfully."
SCORING_URI=$(az ml online-endpoint show \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --name "$ENDPOINT_NAME" \
  --query "scoring_uri" -o tsv)
echo "Scoring URI: ${SCORING_URI}"

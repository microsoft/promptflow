#!/bin/bash
# Deploys the basic-maf workflow as an Azure ML Managed Online Endpoint.
#
# Prerequisites:
#   - az login completed
#   - Azure ML workspace exists
#   - az extension add -n ml
#   - envsubst available (part of gettext)
#
# Usage: bash online-deployment/deploy.sh

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORKFLOW_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "$WORKFLOW_DIR"

SUBSCRIPTION_ID="${SUBSCRIPTION_ID:?Set SUBSCRIPTION_ID}"
RESOURCE_GROUP="${RESOURCE_GROUP:?Set RESOURCE_GROUP}"
WORKSPACE_NAME="${WORKSPACE_NAME:?Set WORKSPACE_NAME}"

export AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:?Set AZURE_OPENAI_ENDPOINT}"
export AZURE_OPENAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:?Set AZURE_OPENAI_DEPLOYMENT}"
export AZURE_OPENAI_API_KEY="${AZURE_OPENAI_API_KEY:?Set AZURE_OPENAI_API_KEY}"
export INSTANCE_TYPE="${INSTANCE_TYPE:-Standard_DS3_v2}"
export INSTANCE_COUNT="${INSTANCE_COUNT:-1}"
export APPLICATIONINSIGHTS_CONNECTION_STRING="${APPLICATIONINSIGHTS_CONNECTION_STRING:-}"

# Render deployment YAML into the same directory (so relative paths resolve correctly)
RENDERED_DEPLOYMENT="${SCRIPT_DIR}/deployment-rendered.yml"
SUBST_VARS='${AZURE_OPENAI_ENDPOINT} ${AZURE_OPENAI_DEPLOYMENT} ${AZURE_OPENAI_API_KEY} ${INSTANCE_TYPE} ${INSTANCE_COUNT} ${APPLICATIONINSIGHTS_CONNECTION_STRING}'
envsubst "$SUBST_VARS" < "${SCRIPT_DIR}/deployment.yml" > "$RENDERED_DEPLOYMENT"

echo "WARNING: ${RENDERED_DEPLOYMENT} may contain API keys. Add to .gitignore."

echo "Creating online endpoint..."
az ml online-endpoint create \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --file "${SCRIPT_DIR}/endpoint.yml" \
  2>/dev/null || echo "Endpoint already exists, continuing..."

echo "Creating deployment..."
az ml online-deployment create \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --file "$RENDERED_DEPLOYMENT" \
  --all-traffic

echo "NOTE: ${RENDERED_DEPLOYMENT} contains secrets. Delete or .gitignore it."

# Smoke test
ENDPOINT_NAME=$(grep '^name:' "${SCRIPT_DIR}/endpoint.yml" | awk '{print $2}')

echo "Running smoke test..."
az ml online-endpoint invoke \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --name "$ENDPOINT_NAME" \
  --request-file <(echo '{"text": "Hello World!"}')

echo ""
echo "Endpoint deployed successfully."
SCORING_URI=$(az ml online-endpoint show \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --name "$ENDPOINT_NAME" \
  --query "scoring_uri" -o tsv)
echo "Scoring URI: ${SCORING_URI}"

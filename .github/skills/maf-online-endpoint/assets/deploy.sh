#!/bin/bash
# Deploys a MAF workflow as an Azure ML Managed Online Endpoint.
#
# Prerequisites:
#   - az login completed
#   - Azure ML workspace already exists
#   - The ml CLI extension is installed: az extension add -n ml
#   - envsubst is available (part of gettext)
#
# NOTE: This script requires Bash (Linux/macOS).  On Windows, run the
# az CLI commands directly in PowerShell — see SKILL.md Step 6, Option B.
#
# Required environment variables:
#   SUBSCRIPTION_ID          - Azure subscription ID
#   RESOURCE_GROUP           - Resource group containing the AML workspace
#   WORKSPACE_NAME           - Azure ML workspace name
#
# Workflow-specific environment variables (uncomment/add as needed):
#   Foundry pattern:  FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL
#   OpenAI pattern:   AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_KEY
#
# Optional environment variables:
#   INSTANCE_TYPE                         - VM SKU (default: Standard_DS3_v2)
#   INSTANCE_COUNT                        - Number of instances (default: 1)
#   APPLICATIONINSIGHTS_CONNECTION_STRING - App Insights connection string
#
# Usage:
#   cd <project-root>
#   bash online-deployment/deploy.sh

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "$PROJECT_ROOT"

SUBSCRIPTION_ID="${SUBSCRIPTION_ID:?Set SUBSCRIPTION_ID}"
RESOURCE_GROUP="${RESOURCE_GROUP:?Set RESOURCE_GROUP}"
WORKSPACE_NAME="${WORKSPACE_NAME:?Set WORKSPACE_NAME}"

# ── Export variables that deployment.yml references via envsubst ──────
export INSTANCE_TYPE="${INSTANCE_TYPE:-Standard_DS3_v2}"
export INSTANCE_COUNT="${INSTANCE_COUNT:-1}"
export APPLICATIONINSIGHTS_CONNECTION_STRING="${APPLICATIONINSIGHTS_CONNECTION_STRING:-}"
# Add workflow-specific variables here, e.g.:
# export AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:?Set AZURE_OPENAI_ENDPOINT}"
# export AZURE_OPENAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:?Set AZURE_OPENAI_DEPLOYMENT}"
# export AZURE_OPENAI_API_KEY="${AZURE_OPENAI_API_KEY:?Set AZURE_OPENAI_API_KEY}"

# ── Render deployment YAML (restricted envsubst preserves $schema) ───
RENDERED_DEPLOYMENT="${SCRIPT_DIR}/deployment-rendered.yml"
# List ONLY the variables your deployment.yml uses:
SUBST_VARS='${INSTANCE_TYPE} ${INSTANCE_COUNT} ${APPLICATIONINSIGHTS_CONNECTION_STRING}'
envsubst "$SUBST_VARS" < "${SCRIPT_DIR}/deployment.yml" > "$RENDERED_DEPLOYMENT"

echo "WARNING: ${RENDERED_DEPLOYMENT} may contain secrets. Add to .gitignore."

# ── Create managed online endpoint ──────────────────────────────────
echo "Creating online endpoint..."
az ml online-endpoint create \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --file "${SCRIPT_DIR}/endpoint.yml" \
  2>/dev/null || echo "Endpoint already exists, continuing..."

# ── Create deployment under the endpoint ─────────────────────────────
# IMPORTANT: Run from the project root so that `code: ..` in the YAML
# resolves correctly (YAML is in online-deployment/, code root is parent).
echo "Creating deployment (this takes 5-10 minutes)..."
az ml online-deployment create \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --file "$RENDERED_DEPLOYMENT" \
  --all-traffic

# ── Smoke test ───────────────────────────────────────────────────────
ENDPOINT_NAME=$(grep '^name:' "${SCRIPT_DIR}/endpoint.yml" | awk '{print $2}')

echo "Running smoke test..."
REQUEST_FILE=$(mktemp --suffix=.json)
echo '{"text": "Hello World!"}' > "$REQUEST_FILE"
az ml online-endpoint invoke \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --name "$ENDPOINT_NAME" \
  --request-file "$REQUEST_FILE"
rm -f "$REQUEST_FILE"

echo ""
echo "Endpoint deployed successfully."
SCORING_URI=$(az ml online-endpoint show \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --name "$ENDPOINT_NAME" \
  --query "scoring_uri" -o tsv)
echo "Scoring URI: ${SCORING_URI}"

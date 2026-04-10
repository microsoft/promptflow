#!/bin/bash
# Builds the container image, pushes it to Azure Container Registry,
# and creates a Container App.
#
# Replaces: Prompt Flow Managed Online Endpoint.
#
# Prerequisites:
#   - az login completed
#   - ACR and Container Apps environment already exist
#   - export AZURE_OPENAI_API_KEY before running
#   - optional: export AZURE_AI_SEARCH_API_KEY for RAG workflows
#   - optional: export APPLICATIONINSIGHTS_CONNECTION_STRING to enable tracing
#   - optional: export MAF_WORKFLOW_FILE to deploy a workflow other than
#               phase-2-rebuild/01_linear_flow.py
#   - or switch to the managed-identity pattern in managed_identity.md
# Usage: bash deploy.sh

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
GUIDE_DIR=$(cd "${SCRIPT_DIR}/../.." && pwd)
cd "$GUIDE_DIR"

[[ -n "${AZURE_OPENAI_API_KEY:-}" ]] || {
  echo "AZURE_OPENAI_API_KEY is required." >&2
  exit 1
}

ACR_NAME="<your-acr>"
RESOURCE_GROUP="<your-rg>"
CONTAINER_APP_ENV="<your-env>"
APP_NAME="maf-app"
OPENAI_ENDPOINT="https://<resource>.openai.azure.com/"
OPENAI_DEPLOYMENT="<deployment>"
SEARCH_ENDPOINT="https://<search>.search.windows.net"
SEARCH_INDEX="<index>"
IMAGE="${ACR_NAME}.azurecr.io/${APP_NAME}:latest"
WORKFLOW_FILE="${MAF_WORKFLOW_FILE:-phase-2-rebuild/01_linear_flow.py}"
HEALTHCHECK_ATTEMPTS="${HEALTHCHECK_ATTEMPTS:-12}"
HEALTHCHECK_SLEEP_SECONDS="${HEALTHCHECK_SLEEP_SECONDS:-10}"

SECRET_ARGS=(
  openai-key="$AZURE_OPENAI_API_KEY"
)

ENV_ARGS=(
  AZURE_OPENAI_API_KEY=secretref:openai-key
  AZURE_OPENAI_ENDPOINT="$OPENAI_ENDPOINT"
  AZURE_OPENAI_CHAT_DEPLOYMENT_NAME="$OPENAI_DEPLOYMENT"
  MAF_WORKFLOW_FILE="$WORKFLOW_FILE"
)

if [[ -n "${AZURE_AI_SEARCH_API_KEY:-}" ]]; then
  SECRET_ARGS+=(search-key="$AZURE_AI_SEARCH_API_KEY")
  ENV_ARGS+=(
    AZURE_AI_SEARCH_ENDPOINT="$SEARCH_ENDPOINT"
    AZURE_AI_SEARCH_INDEX_NAME="$SEARCH_INDEX"
    AZURE_AI_SEARCH_API_KEY=secretref:search-key
  )
fi

if [[ -n "${APPLICATIONINSIGHTS_CONNECTION_STRING:-}" ]]; then
  SECRET_ARGS+=(appinsights-conn="$APPLICATIONINSIGHTS_CONNECTION_STRING")
  ENV_ARGS+=(APPLICATIONINSIGHTS_CONNECTION_STRING=secretref:appinsights-conn)
fi

az acr build \
  --registry "$ACR_NAME" \
  --image "${APP_NAME}:latest" \
  --file phase-4-migrate-ops/4b-deployment/Dockerfile \
  .

az containerapp create \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$CONTAINER_APP_ENV" \
  --image "$IMAGE" \
  --target-port 8000 \
  --ingress external \
  --registry-server "${ACR_NAME}.azurecr.io" \
  --secrets "${SECRET_ARGS[@]}" \
  --env-vars "${ENV_ARGS[@]}"

APP_URL=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

healthy=false
for ((i = 1; i <= HEALTHCHECK_ATTEMPTS; i++)); do
  if curl --silent --fail "https://${APP_URL}/health" >/dev/null; then
    healthy=true
    break
  fi
  sleep "$HEALTHCHECK_SLEEP_SECONDS"
done

if [[ "$healthy" != true ]]; then
  echo "Container App did not become healthy in time: https://${APP_URL}/health" >&2
  exit 1
fi

curl --fail-with-body -X POST "https://${APP_URL}/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the refund policy?"}' | python3 -m json.tool

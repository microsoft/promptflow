#!/bin/bash
# Builds the container image, pushes it to Azure Container Registry,
# and creates a Container App.
#
# Replaces: Prompt Flow Managed Online Endpoint.
#
# Prerequisites:
#   - az login completed
#   - ACR and Container Apps environment already exist
#   - Replace all <...> placeholders in this script with your values
#   - optional: export AZURE_AI_SEARCH_API_KEY for RAG workflows
#   - optional: export APPLICATIONINSIGHTS_CONNECTION_STRING to enable tracing
#   - optional: export MAF_WORKFLOW_FILE to deploy a workflow other than
#               phase-2-rebuild/01_linear_flow.py
#   - The Container App uses DefaultAzureCredential to authenticate with
#     the Foundry project endpoint. Assign a managed identity with the
#     appropriate role — see managed_identity.md for details.
# Usage: bash deploy.sh

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
GUIDE_DIR=$(cd "${SCRIPT_DIR}/../.." && pwd)
cd "$GUIDE_DIR"

ACR_NAME="<your-acr>"
RESOURCE_GROUP="<your-rg>"
CONTAINER_APP_ENV="<your-env>"
APP_NAME="maf-app"
FOUNDRY_ENDPOINT="https://<resource>.services.ai.azure.com"
FOUNDRY_MODEL_NAME="<model>"
SEARCH_ENDPOINT="https://<search>.search.windows.net"
SEARCH_INDEX="<index>"
IMAGE="${ACR_NAME}.azurecr.io/${APP_NAME}:latest"
WORKFLOW_FILE="${MAF_WORKFLOW_FILE:-phase-2-rebuild/01_linear_flow.py}"
HEALTHCHECK_ATTEMPTS="${HEALTHCHECK_ATTEMPTS:-12}"
HEALTHCHECK_SLEEP_SECONDS="${HEALTHCHECK_SLEEP_SECONDS:-10}"

# Fail fast if placeholders have not been replaced.
for var_name in ACR_NAME RESOURCE_GROUP CONTAINER_APP_ENV FOUNDRY_ENDPOINT FOUNDRY_MODEL_NAME; do
  eval "val=\$$var_name"
  if [[ "$val" == *"<"* ]]; then
    echo "ERROR: $var_name still contains a placeholder value ('$val')." >&2
    echo "Edit deploy.sh and replace all <...> placeholders before running." >&2
    exit 1
  fi
done

SECRET_ARGS=()

ENV_ARGS=(
  FOUNDRY_PROJECT_ENDPOINT="$FOUNDRY_ENDPOINT"
  FOUNDRY_MODEL="$FOUNDRY_MODEL_NAME"
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

CREATE_ARGS=(
  az containerapp create
  --name "$APP_NAME"
  --resource-group "$RESOURCE_GROUP"
  --environment "$CONTAINER_APP_ENV"
  --image "$IMAGE"
  --target-port 8000
  --ingress external
  --registry-server "${ACR_NAME}.azurecr.io"
  --env-vars "${ENV_ARGS[@]}"
)
if [[ ${#SECRET_ARGS[@]} -gt 0 ]]; then
  CREATE_ARGS+=(--secrets "${SECRET_ARGS[@]}")
fi

"${CREATE_ARGS[@]}"

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

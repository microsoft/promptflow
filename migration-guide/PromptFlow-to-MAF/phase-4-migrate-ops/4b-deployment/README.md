# Deploying a MAF Workflow as an Azure ML Managed Online Endpoint

This guide walks through deploying a Microsoft Agent Framework (MAF) workflow
to an **Azure Machine Learning Managed Online Endpoint**, replacing the
Prompt Flow Managed Online Endpoint pattern.

> **Tip for AI agents / Copilot users:** Use the [`maf-online-endpoint`](../../../.github/skills/maf-online-endpoint/SKILL.md)
> skill to scaffold this deployment automatically. The skill wraps any MAF
> workflow into an `init()` / `run()` scoring script and generates the
> `endpoint.yml`, `deployment.yml`, `conda.yml`, `score.py`, and `deploy.sh`
> files described below, plus the required RBAC assignments. Trigger it with
> prompts like *"deploy this MAF workflow as a managed online endpoint"* or
> *"create an online endpoint for my agent-framework workflow"*. The manual
> steps below remain useful for understanding or customizing the output.

## Files Overview

| File | Purpose |
|------|---------|
| `endpoint.yml` | Endpoint definition (name, auth mode) |
| `deployment.yml` | Deployment template (environment, code, instance config) — uses `${VAR}` placeholders |
| `score.py` | Scoring script with `init()` / `run()` entry points |
| `conda.yml` | Conda environment with pip dependencies |
| `deploy.sh` | End-to-end deployment script |

## Prerequisites

- **Azure CLI** with the `ml` extension installed:
  ```bash
  az extension add --name ml --yes
  ```
- An existing **Azure ML workspace**
- A **Foundry project** with a deployed model
- `envsubst` available (part of `gettext`; used by `deploy.sh`)
- Logged in: `az login`

## Step 1 — Set Environment Variables

Required:

```bash
export SUBSCRIPTION_ID="<your-subscription-id>"
export RESOURCE_GROUP="<your-resource-group>"
export WORKSPACE_NAME="<your-workspace>"
export FOUNDRY_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
export FOUNDRY_MODEL="gpt-4o"
```

Optional:

```bash
export MAF_WORKFLOW_FILE="phase-2-rebuild/01_linear_flow.py"   # default
export INSTANCE_TYPE="Standard_DS3_v2"                         # default
export INSTANCE_COUNT="1"                                      # default
export AZURE_AI_SEARCH_ENDPOINT="https://..."                  # for RAG workflows
export AZURE_AI_SEARCH_INDEX_NAME="my-index"
export AZURE_AI_SEARCH_API_KEY="..."
export APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=..."  # for tracing
```

## Step 2 — Create the Online Endpoint

```bash
az ml online-endpoint create \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --file phase-4-migrate-ops/4b-deployment/endpoint.yml
```

This creates an endpoint named `maf-endpoint` with key-based auth. The
endpoint has a system-assigned managed identity.

## Step 3 — Assign RBAC to the Endpoint Identity

The endpoint's managed identity needs permission to call the Foundry model.
Get the identity's principal ID:

```bash
az ml online-endpoint show \
  --subscription "$SUBSCRIPTION_ID" \
  --name maf-endpoint \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --query identity.principal_id -o tsv
```

Assign the **Cognitive Services User** role on the Foundry resource:

```bash
az role assignment create \
  --assignee-object-id <principal-id> \
  --assignee-principal-type ServicePrincipal \
  --role "Cognitive Services User" \
  --scope "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>"
```

> **Note:** The `Azure AI Developer` role does _not_ include the
> `Microsoft.CognitiveServices/accounts/AIServices/agents/write` data action
> required by Foundry. Use `Cognitive Services User` (which has the wildcard
> `Microsoft.CognitiveServices/*`) or `Azure AI Owner`.

Allow **5–10 minutes** for RBAC data plane propagation before testing.

## Step 4 — Render and Create the Deployment

`deployment.yml` is a template with `${VAR}` placeholders. The deploy script
renders it with `envsubst` and then creates the deployment:

```bash
# Render
envsubst '$FOUNDRY_PROJECT_ENDPOINT $FOUNDRY_MODEL ...' \
  < deployment.yml > deployment-rendered.yml

# Create
az ml online-deployment create \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --file deployment-rendered.yml \
  --all-traffic
```

Key deployment settings:
- **Base image:** `mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04:latest`
- **Conda environment:** installs `agent-framework`, `azureml-inference-server-http`, etc.
- **Request timeout:** 60 000 ms (LLM calls need more than the 5 s default)
- **Code root:** the `PromptFlow-to-MAF` directory (so the scoring script can
  import `workflow_loader` and the workflow files)

## Step 5 — Smoke Test

```bash
az ml online-endpoint invoke \
  --subscription "$SUBSCRIPTION_ID" \
  --name maf-endpoint \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --request-file <(echo '{"question": "What is the refund policy?"}')
```

Expected response:

```json
{"answer": "..."}
```

## One-Command Deploy

`deploy.sh` automates all of the above (Steps 2–5):

```bash
export SUBSCRIPTION_ID=... RESOURCE_GROUP=... WORKSPACE_NAME=... FOUNDRY_PROJECT_ENDPOINT=... FOUNDRY_MODEL=...
bash phase-4-migrate-ops/4b-deployment/deploy.sh
```

## Scoring Script Pattern

The scoring script (`score.py`) follows the AML `init()` / `run()` convention:

- **`init()`** — called once at container startup. Loads the MAF workflow via
  `workflow_loader` and optionally configures Application Insights tracing.
- **`run(raw_data)`** — called per request. Parses JSON `{"question": "..."}`,
  runs the workflow, and returns `{"answer": "..."}`.

`AgentResponse` objects returned by the workflow are not JSON-serializable, so
the script extracts `.text` before returning.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 PermissionDenied` / `AIServices/agents/write` | Endpoint identity missing RBAC | Assign `Cognitive Services User` on the Foundry resource |
| `upstream request timeout` | Default 5 s timeout too short for LLM | Set `request_timeout_ms: 60000` in deployment YAML |
| `AgentResponse is not JSON serializable` | `run()` returns non-serializable object | Extract `.text` from the response |
| `pip_requirements` validation error | Not a valid field for inline environment | Use `conda_file` with `name` + `version` instead |
| Image build fails on package version | Package version not on PyPI | Remove version constraints from `conda.yml` |

## Cleanup

```bash
az ml online-endpoint delete \
  --subscription "$SUBSCRIPTION_ID" \
  --name maf-endpoint \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --yes
```

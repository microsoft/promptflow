---
name: maf-online-endpoint
description: "Deploy a Microsoft Agent Framework (MAF) workflow as an Azure ML managed online endpoint. Wraps any workflow into an init()/run() scoring script, creates conda environment, endpoint and deployment YAMLs, deploy script, and assigns RBAC. Supports managed identity auth and Application Insights tracing. WHEN: deploy MAF workflow, deploy agent-framework workflow, create online endpoint for MAF, deploy workflow to AML, managed online endpoint for agent workflow, wrap workflow in scoring script, deploy agent as endpoint."
---

# Deploy MAF Workflow as Azure ML Managed Online Endpoint

This skill wraps a Microsoft Agent Framework (`agent-framework`) workflow into
an Azure ML managed online endpoint using the standard scoring-script pattern
(`init()` / `run()`), following the patterns from the
[azureml-examples managed endpoint samples](https://github.com/Azure/azureml-examples/tree/main/sdk/python/endpoints/online/managed).

## Overview

The deployment creates all files in an `online-deployment/` subdirectory under
the project root:

```
<project-root>/
  workflow.py              ← the MAF workflow
  online-deployment/
    score.py               ← scoring script
    conda.yml              ← conda environment
    endpoint.yml           ← endpoint config
    deployment.yml         ← deployment template (${VAR} placeholders)
    deploy.sh              ← deploy script (Bash; see notes for Windows)
```

1. **Scoring script** (`score.py`) — `init()` loads the workflow at startup;
   `run()` handles each request.
2. **Conda environment** (`conda.yml`) — Python 3.11 with agent-framework and
   azureml-inference-server-http.
3. **Endpoint YAML** (`endpoint.yml`) — endpoint name and auth mode.
4. **Deployment YAML** (`deployment.yml`) — template with `${VAR}` placeholders
   for environment variables, instance config, and request settings.
5. **Deploy script** (`deploy.sh`) — renders the template, creates the endpoint
   and deployment, runs a smoke test.

> **Path resolution rule:** AML CLI resolves `conda_file`, `code`, and
> `scoring_script` paths **relative to the YAML file location**, not the CWD.
> Since the YAML is inside `online-deployment/`, use `conda_file: conda.yml`
> (same directory) and `code: ..` (parent = project root).

## Agent Interaction Pattern

When the user asks to deploy a MAF workflow as an online endpoint:

1. **Ask** for infrastructure variables (Step 0 §A) using `vscode_askQuestions`:
   subscription, resource group, workspace, and the workflow file path.
2. **Read** the workflow file. Inspect imports and `os.environ`/`os.getenv`
   calls to discover what the workflow needs (Step 0 §B).
3. **Ask** the user to provide values for any workflow-specific variables that
   have no defaults.
4. **Generate** the files from the templates in [./assets/](./assets/) into an
   `online-deployment/` subdirectory under the project root.
5. **Run** deployment commands via terminal.  On Windows, run `az` CLI commands
   directly in PowerShell (the Bash `deploy.sh` won't work).  On Linux/macOS,
   use `deploy.sh` or run the commands directly.
6. **Assign RBAC** (Step 7) — only needed for managed-identity workflows
   (Foundry/DefaultAzureCredential).  Skip for API-key workflows.
7. **Wait** 5–10 minutes for RBAC propagation (if applicable), then run smoke
   test.
8. **Report** the scoring URI and remind user to `.gitignore` rendered YAML
   files that contain secrets.

## Step 0 — Gather Required Information

### A. Online Endpoint Infrastructure (always required)

| Variable | Description | Default |
|----------|-------------|---------|
| `SUBSCRIPTION_ID` | Azure subscription containing the AML workspace | _(required)_ |
| `RESOURCE_GROUP` | Resource group with the AML workspace | _(required)_ |
| `WORKSPACE_NAME` | Azure ML workspace name | _(required)_ |
| `ENDPOINT_NAME` | Name of the online endpoint | `maf-endpoint` |
| `DEPLOYMENT_NAME` | Deployment name under the endpoint | `blue` |
| `INSTANCE_TYPE` | VM SKU | `Standard_DS3_v2` |
| `INSTANCE_COUNT` | Number of instances | `1` |
| `REQUEST_TIMEOUT_MS` | Request timeout in ms | `60000` |

### B. Workflow Requirements (depends on the workflow)

Read the user's workflow file and inspect:

1. **Imports** — determine pip packages for `conda.yml`.
2. **`os.environ[...]` / `os.getenv(...)` calls** — determine environment
   variables the deployment must inject.
3. **Credential usage** — `DefaultAzureCredential` / `ManagedIdentityCredential`
   means RBAC must be set up; an API key means a secret env var.

#### Common workflow patterns

| Pattern | Imports | Required env vars | Extra pip packages | RBAC role |
|---------|---------|--------------------|--------------------|-----------|
| **Foundry LLM** | `FoundryChatClient`, `DefaultAzureCredential` | `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL` | `agent-framework` | `Cognitive Services User` |
| **OpenAI API key** | `OpenAIChatClient` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_KEY` | `agent-framework`, `agent-framework-openai` | _(none — uses API key)_ |
| **RAG (AI Search)** | `AzureAISearchContextProvider` | above + `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_AI_SEARCH_INDEX_NAME`, `AZURE_AI_SEARCH_API_KEY` | above + `agent-framework-azure-ai-search` | above (Search uses API key) |
| **Function tools** | plain Python functions | same as Foundry LLM | same as Foundry LLM | same as Foundry LLM |

### C. RBAC (after endpoint is created)

Get endpoint managed identity principal ID:
```bash
az ml online-endpoint show --name <endpoint> --query identity.principal_id -o tsv
```

### D. Optional (cross-cutting)

| Variable | Default | Description |
|----------|---------|-------------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | _(empty)_ | Enables OpenTelemetry tracing |

## Step 1 — Generate the Scoring Script

Use the template at [./assets/score.py](./assets/score.py).

**Key decisions:**
- `AgentResponse` is not JSON-serializable → extract `.text` before returning.
- `project_root = Path(__file__).resolve().parents[1]` — `score.py` is one
  level deep (`online-deployment/score.py`), so `parents[1]` reaches the
  project root.  Adjust if your layout differs.
- `asyncio.get_event_loop().run_until_complete()` bridges the sync `run()` to
  the async workflow.
- Optional Application Insights tracing configured via env var.
- **Input key:** Inspect the workflow to determine what key to parse from the
  request body (e.g. `"text"`, `"question"`).  Adapt accordingly.
- **Direct import vs loader:** For simple projects with a single `workflow.py`
  at the project root, use `from workflow import workflow as wf` directly.  For
  complex projects with multiple workflow files, use `workflow_loader.py`
  (Step 2).

## Step 2 — Generate the Workflow Loader (Optional)

If the project has multiple workflow files or needs runtime selection, generate
`workflow_loader.py` at the project root.  It dynamically imports a Python file
that defines a module-level `workflow` object.
See [./assets/workflow_loader.py](./assets/workflow_loader.py).

For simple projects with a single workflow, **skip this step** and import the
workflow directly in `score.py`.

## Step 3 — Generate `conda.yml`

Use the template at [./assets/conda.yml](./assets/conda.yml).

**Important:**
- Do NOT pin version constraints unless the user specifies them. Packages like
  `agent-framework-azure-ai-search` may not have published version ranges on
  PyPI, which causes image build failures.
- Only include packages the workflow actually uses.  For OpenAI API key
  workflows, include `agent-framework-openai` but omit
  `agent-framework-azure-ai-search` and `azure-monitor-opentelemetry` unless
  needed.

## Step 4 — Generate `endpoint.yml`

Use the template at [./assets/endpoint.yml](./assets/endpoint.yml).

## Step 5 — Generate `deployment.yml` (Template)

Use the template at [./assets/deployment.yml](./assets/deployment.yml).

**Critical — path resolution:**
AML CLI resolves all relative paths in the deployment YAML **relative to the
YAML file's location**, not the working directory.  Since deployment files live
in `online-deployment/`:

```yaml
environment:
  conda_file: conda.yml               # ← same dir as deployment.yml
code_configuration:
  code: ..                             # ← parent dir = project root
  scoring_script: online-deployment/score.py  # ← relative to code root
```

Getting this wrong causes a double-nesting error like
`online-deployment/online-deployment/conda.yml`.

**Other key settings:**
- `request_timeout_ms: 60000` — LLM calls typically take 5–30 s; the AML
  default of 5 s causes timeouts.
- Use `conda_file` (not `pip_requirements`) — the latter is not valid for
  inline environment definitions.
- When rendering with `envsubst`, use a **restricted variable list** so
  `$schema` is not eaten.
- Only include env vars the workflow actually needs; omit unused ones.

**Security:** The rendered YAML (`deployment-rendered.yml`) may contain API
keys in plaintext.  Add it to `.gitignore` or delete it after deployment.

## Step 6 — Deploy

### Option A: Bash script (Linux/macOS)

Use the template at [./assets/deploy.sh](./assets/deploy.sh).  Requires
`envsubst` (part of `gettext`).

### Option B: Direct CLI commands (Windows / any OS)

On Windows, `deploy.sh` won't work (`envsubst`, `mktemp`, process substitution
are unavailable).  Instead, run the steps directly in PowerShell:

```powershell
# 1. Render deployment YAML (replace placeholders with actual values)
$content = Get-Content online-deployment/deployment.yml -Raw
$content = $content -replace '\$\{AZURE_OPENAI_ENDPOINT\}', $env:AZURE_OPENAI_ENDPOINT
# ... repeat for each placeholder ...
Set-Content -Path online-deployment/deployment-rendered.yml -Value $content

# 2. Create endpoint
az ml online-endpoint create `
  --subscription $SUBSCRIPTION_ID `
  --resource-group $RESOURCE_GROUP `
  --workspace-name $WORKSPACE_NAME `
  --file online-deployment/endpoint.yml

# 3. Create deployment (run from the project root directory!)
az ml online-deployment create `
  --subscription $SUBSCRIPTION_ID `
  --resource-group $RESOURCE_GROUP `
  --workspace-name $WORKSPACE_NAME `
  --file online-deployment/deployment-rendered.yml `
  --all-traffic

# 4. Smoke test
Set-Content -Path online-deployment/request.json -Value '{"text": "Hello"}'
az ml online-endpoint invoke `
  --subscription $SUBSCRIPTION_ID `
  --resource-group $RESOURCE_GROUP `
  --workspace-name $WORKSPACE_NAME `
  --name <ENDPOINT_NAME> `
  --request-file online-deployment/request.json
```

> **Important:** Run the `az ml online-deployment create` command from the
> **project root** directory, not from inside `online-deployment/`.  The CLI
> resolves `code: ..` relative to the YAML file, but the CWD also matters for
> finding the YAML file itself.

## Step 7 — RBAC for Managed Identity

After the endpoint is created, its system-assigned managed identity needs
the **`Cognitive Services User`** role on the Foundry resource.

```bash
# Get principal ID
PRINCIPAL_ID=$(az ml online-endpoint show \
  --subscription "$SUBSCRIPTION_ID" \
  --name <ENDPOINT_NAME> \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --query identity.principal_id -o tsv)

# Assign role
az role assignment create \
  --assignee-object-id "$PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Cognitive Services User" \
  --scope "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>"
```

**Why `Cognitive Services User`?**
- `Azure AI Developer` does **not** include `Microsoft.CognitiveServices/accounts/AIServices/agents/write`.
- `Cognitive Services User` has the wildcard `Microsoft.CognitiveServices/*`.
- Allow **5–10 minutes** for RBAC data plane propagation.

See [./references/managed-identity.md](./references/managed-identity.md) for full details.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No such file: .../online-deployment/online-deployment/conda.yml` | Paths in deployment YAML resolved relative to YAML location, not CWD | Use `conda_file: conda.yml` and `code: ..` when YAML is in a subdirectory |
| `401 PermissionDenied` | Missing RBAC | Assign `Cognitive Services User` on Foundry resource |
| `upstream request timeout` | 5 s default too short | `request_timeout_ms: 60000` |
| `AgentResponse is not JSON serializable` | Returning raw workflow output | Extract `.text` from the response |
| `pip_requirements` validation error | Invalid field for inline env | Use `conda_file` instead |
| Image build fails on version constraints | Package not on PyPI with that version | Remove version pins from `conda.yml` |
| `$schema` missing after envsubst | Unrestricted envsubst eats `$schema` | Use restricted variable list |
| `FileNotFoundError: az` (Windows subprocess) | `az` is a `.cmd` file on Windows | Use `shell=True` in `subprocess.run` |
| `envsubst` not found (Windows) | `envsubst` is a Linux tool | Use PowerShell string replacement (see Step 6 Option B) |

See [./references/troubleshooting.md](./references/troubleshooting.md) for extended diagnostics.

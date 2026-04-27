# Troubleshooting MAF Online Endpoint Deployments

## Common Issues

### 1. Path double-nesting: `online-deployment/online-deployment/conda.yml`

**Cause:** AML CLI resolves `conda_file`, `code`, and `scoring_script` paths
**relative to the YAML file's location**, not the working directory.  If the
deployment YAML is in `online-deployment/` and specifies
`conda_file: online-deployment/conda.yml`, it resolves to
`online-deployment/online-deployment/conda.yml`.

**Fix:** Use paths relative to the YAML file's directory:
```yaml
# deployment.yml is in online-deployment/
environment:
  conda_file: conda.yml           # same dir as deployment.yml
code_configuration:
  code: ..                         # parent dir = project root
  scoring_script: online-deployment/score.py  # relative to code root
```

### 2. `401 PermissionDenied` / `AIServices/agents/write`

**Cause:** The endpoint's managed identity does not have the correct RBAC role
on the Foundry resource.

**Fix:**
```bash
# Get endpoint identity
PRINCIPAL_ID=$(az ml online-endpoint show \
  --name maf-endpoint \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --query identity.principal_id -o tsv)

# Assign Cognitive Services User (not Azure AI Developer)
az role assignment create \
  --assignee-object-id "$PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Cognitive Services User" \
  --scope "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>"
```

Allow **5–10 minutes** for RBAC data plane propagation.

### 3. `upstream request timeout`

**Cause:** The default AML request timeout is 5 seconds, which is too short
for LLM calls (typically 5–30 s).

**Fix:** Set `request_timeout_ms: 60000` in `deployment.yml`:
```yaml
request_settings:
  request_timeout_ms: 60000
```

### 4. `AgentResponse is not JSON serializable`

**Cause:** The `run()` function returns a raw `AgentResponse` object.

**Fix:** Extract `.text` before returning:
```python
output = outputs[0]
if hasattr(output, "text"):
    return {"answer": output.text}
return {"answer": str(output)}
```

### 5. `pip_requirements` validation error

**Cause:** `pip_requirements` is not a valid field for inline environment
definitions in AML deployment YAML.

**Fix:** Use `conda_file` with a full conda environment definition:
```yaml
environment:
  name: maf-env
  version: "1"
  image: mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04:latest
  conda_file: conda.yml
```

### 6. Image build fails on package version

**Cause:** A pinned version constraint references a version that doesn't exist
on PyPI for that package.

**Fix:** Remove version constraints from `conda.yml`:
```yaml
# Bad
- agent-framework-azure-ai-search==1.0.0

# Good
- agent-framework-azure-ai-search
```

### 7. `$schema` missing after envsubst

**Cause:** Unrestricted `envsubst` treats `$schema` as a variable and replaces
it with an empty string.

**Fix:** Use a restricted variable list:
```bash
SUBST_VARS='${FOUNDRY_PROJECT_ENDPOINT} ${FOUNDRY_MODEL} ...'
envsubst "$SUBST_VARS" < deployment.yml > deployment-rendered.yml
```

### 8. Workflow import errors at container startup

**Cause:** The `sys.path` depth in `score.py` doesn't match the project layout,
so `workflow_loader` cannot be imported.

**Fix:** Adjust the `parents[N]` depth in `score.py`:
```python
# If score.py is at project/deployment/score.py (1 level deep)
project_root = Path(__file__).resolve().parents[1]

# If score.py is at project/phase-4/deployment/score.py (2 levels deep)
project_root = Path(__file__).resolve().parents[2]
```

### 9. Windows-specific issues

**`FileNotFoundError: az` in subprocess:**
On Windows, `az` is a batch file (`az.cmd`), not a direct executable.  Use
`shell=True` in `subprocess.run()` calls.

**`envsubst` not found:**
`envsubst` is a Linux tool (part of `gettext`).  On Windows, use PowerShell
string replacement instead:
```powershell
$content = Get-Content deployment.yml -Raw
$content = $content -replace '\$\{VAR_NAME\}', $actualValue
Set-Content -Path deployment-rendered.yml -Value $content
```

**Process substitution `<(...)` not available:**
Write request payloads to a temp file instead:
```powershell
Set-Content -Path request.json -Value '{"text": "Hello"}'
az ml online-endpoint invoke ... --request-file request.json
```

## Checking Deployment Logs

```bash
# Get deployment logs
az ml online-deployment get-logs \
  --name blue \
  --endpoint-name maf-endpoint \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --lines 100
```

Or via Python SDK:
```python
ml_client.online_deployments.get_logs(
    name="blue",
    endpoint_name="maf-endpoint",
    lines=100,
)
```

## Checking Endpoint Health

```bash
az ml online-endpoint show \
  --name maf-endpoint \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE_NAME" \
  --query "{name:name, state:provisioning_state, scoring_uri:scoring_uri, traffic:traffic}"
```

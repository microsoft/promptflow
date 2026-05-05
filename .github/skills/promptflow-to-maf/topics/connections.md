# Connections (Credentials)

> **Read this when** the source flow references one or more PromptFlow connections (any LLM node has a `connection:` field, or any custom-tool node passes a `connection: ...` input).

MAF has **no first-class "connection" entity**. There is no encrypted store, no `pf connection create`, no name-based reference. Credentials are passed directly to the SDK clients you instantiate. Your job during conversion is to:

1. **Detect** what kind of credential each PF connection holds (API key vs Microsoft Entra / managed identity vs custom key/value).
2. **Emit** the right MAF client constructor template.
3. **Communicate** to the customer which environment variables they must populate.

You almost never need to ask the user — the auth mode is discoverable from the PF artifacts.

---

## Step 1 — Detect the auth mode (deterministic)

Try each source in order; stop at the first that resolves.

### A. Local connection YAML in the repo
PF connection YAMLs encode auth mode explicitly. Search the repo for `*.yml` / `*.yaml` files with `$schema: .../<...>Connection.schema.json` or `type: azure_open_ai|open_ai|serverless|custom`.

```yaml
# Key-based
type: azure_open_ai
api_key: "${env:AOAI_KEY}"           # or a literal value
api_base: "https://x.openai.azure.com/"
api_version: "2024-02-15-preview"
```

```yaml
# Microsoft Entra / managed identity
type: azure_open_ai
auth_mode: meid_token                # <-- the tell (also seen as 'aad')
api_base: "https://x.openai.azure.com/"
api_version: "2024-02-15-preview"
```

### B. The PF / AML store
If no YAML is in the repo (typical — secrets live in PF or Foundry), resolve the connection name from the LLM node's `connection:` field and run **one** of:

```bash
pf connection show -n <conn_name> --output json
az ml connection show -n <conn_name> -g <rg> -w <ws> -o json
```

The returned object exposes `auth_mode` and whether `api_key` / `credentials` are populated.

### C. Environment hints (last resort)
When (A) and (B) are unavailable, scan `.env`, `.env.example`, deployment YAMLs, and CI workflow files:

- `AZURE_OPENAI_API_KEY` (or similar) present and non-empty → **key**
- Key absent but `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `MSI_ENDPOINT` set, or comments mentioning `meid_token` / `managed identity` / `DefaultAzureCredential` → **identity**

### Decision rule

| Signal | Auth mode |
|---|---|
| `auth_mode: meid_token` (or `aad`) | Entra / managed identity |
| `api_key` populated, no `auth_mode` | API key |
| `type: open_ai` (non-Azure) with `api_key` | OpenAI key (no identity option) |
| `type: serverless` with `api_key` | Serverless key |
| `type: custom` | See [Custom connections](#custom-connections) below |
| Ambiguous / unresolved | Default to **identity** + emit a `# TODO(migration)` marker; never silently emit a key path that requires a value the customer doesn't have |

---

## Step 2 — Emit the right MAF client template

> The base client class is `OpenAIChatClient` for both Azure and non-Azure OpenAI. There is **no** separate `AzureOpenAIChatClient`. Pass `azure_endpoint=...` to route to Azure.

### Template — Azure OpenAI, key

```python
import os
from agent_framework.openai import OpenAIChatClient

client = OpenAIChatClient(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
)
```
`.env.example` adds `AZURE_OPENAI_API_KEY=...` as **required**.

### Template — Azure OpenAI, Microsoft Entra / managed identity

```python
import os
from azure.identity.aio import DefaultAzureCredential
from agent_framework.openai import OpenAIChatClient

credential = DefaultAzureCredential()
client = OpenAIChatClient(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
    credential=credential,
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
)
```
`.env.example` **omits** `AZURE_OPENAI_API_KEY`. Add to README:
> This deployment uses Microsoft Entra ID. Locally, sign in with `az login`. In Azure, assign the deployment's managed identity the **Cognitive Services OpenAI User** role on the AOAI resource.

Add `azure-identity>=1.15.0` to `requirements.txt`.

### Template — OpenAI (non-Azure)

Always key; there is no managed-identity option.

```python
client = OpenAIChatClient(
    model=os.environ["OPENAI_MODEL"],
    api_key=os.environ["OPENAI_API_KEY"],
)
```

### Template — Serverless / Foundry-deployed model

Same as Azure OpenAI: key path uses `api_key`; identity path uses `credential=DefaultAzureCredential()`. Point `azure_endpoint` (or the equivalent argument for the client you choose) at the serverless URL.

---

## Custom connections

PF `CustomConnection` is a free-form bag of `configs` (non-secret) and `secrets`. Map it to a small typed config object loaded from environment variables. Do **not** invent a fake `CustomConnection` class in MAF.

### Pattern — `pydantic-settings`

```python
# mysvc_config.py
from pydantic import Field
from pydantic_settings import BaseSettings

class MyServiceConfig(BaseSettings):
    endpoint: str = Field(..., description="Service endpoint URL")
    api_key: str = Field(..., description="API key (was secrets.my_key in PF)")
    other_config: str = "default"

    model_config = {"env_prefix": "MYSVC_", "env_file": ".env", "extra": "ignore"}
```

```python
# in the Executor
from .mysvc_config import MyServiceConfig

class MyToolExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cfg = MyServiceConfig()  # raises ValidationError listing missing vars
```

`.env.example` lists `MYSVC_ENDPOINT`, `MYSVC_API_KEY`, etc., grouped under a comment naming the original PF connection.

> If the custom tool already reads its credentials from environment variables itself (common in internal LLM gateways — see [topics/custom-tool-nodes.md](custom-tool-nodes.md)), you may not need a config object at all. Just document the env vars in `.env.example`.

---

## Step 3 — Communicate setup to the customer

After conversion the customer no longer has `pf connection list`. Make the requirements **discoverable**, **validated**, and **self-documenting**.

### 3a. Always emit `.env.example`

Group variables by the original PF connection name in comments:

```env
# === Azure OpenAI (was PF connection: my_aoai, auth_mode: key) ===
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_API_KEY=                 # required

# === Azure AI Search (was PF connection: my_search) ===
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_API_KEY=

# === Tracing (optional) ===
APPLICATIONINSIGHTS_CONNECTION_STRING=
```

For identity-based deployments, leave the key var **out** entirely and add a one-line comment explaining the auth model.

### 3b. Always emit a README "Configuration" section

Include a mapping table so PF users recognize what each env var replaces:

```markdown
## Configuration

This workflow needs the following credentials (previously stored as PF connections):

| PF connection (old) | Env var (new) | Required | Notes |
|---|---|---|---|
| `my_aoai` | `AZURE_OPENAI_ENDPOINT` | yes |  |
|  | `AZURE_OPENAI_DEPLOYMENT` | yes |  |
|  | `AZURE_OPENAI_API_KEY` | yes\* | \* only if not using managed identity |
| `my_search` | `AZURE_SEARCH_ENDPOINT` | yes |  |
|  | `AZURE_SEARCH_API_KEY` | yes |  |

Set them via `.env` (local) or container/app settings (production).
```

### 3c. Fail fast at startup (recommended)

Don't let a missing key surface deep inside an SDK call. Validate in the Executor's `__init__` or at module import:

```python
_REQUIRED = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT"]
_missing = [k for k in _REQUIRED if not os.environ.get(k)]
if _missing:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(_missing)}.\n"
        f"See README 'Configuration' or copy .env.example to .env."
    )
```

When using `pydantic-settings`, you get this for free.

### 3d. Surface in deployment artifacts

- **AML deployment YAML** — declare expected env vars under `environment_variables:` so the deployment fails to create if an op forgets one.
- **CI workflows** — map secrets to the same names so a missing secret breaks the pipeline early, not at runtime.
- **Dockerfile / conda.yml** — comment the expected env vars at the top.

### 3e. Optional — `check-config` doctor command

Helpful for non-trivial flows. A tiny script the customer can run before invoking the workflow:

```python
# python -m my_workflow.check_config
import sys
from .settings import Settings

def main() -> None:
    try:
        Settings()
        print("✓ All required configuration present")
    except Exception as e:
        print(f"✗ Configuration error:\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## Conversion algorithm (summary)

```text
for each LLM / custom-tool node N referencing a PF connection:
    conn_name = N.connection or N.inputs.connection
    conn = (
        load_local_connection_yaml(repo, conn_name)
        or pf_connection_show(conn_name)
        or aml_connection_show(conn_name, ws)
        or infer_from_env_files(repo)
    )

    if conn is None:
        emit_identity_template(default=True)
        add_TODO_comment("could not resolve connection; verify auth mode")
        continue

    if conn.type in ("azure_open_ai", "serverless"):
        if conn.auth_mode in ("meid_token", "aad") or conn.api_key is None:
            emit_identity_template(conn)
        else:
            emit_key_template(conn)
    elif conn.type == "open_ai":
        emit_openai_key_template(conn)
    elif conn.type == "custom":
        emit_settings_object(conn)              # pydantic-settings or dataclass

    update_env_example(conn)
    update_readme_config_table(conn)
```

---

## Edge cases

- **Hybrid `auth_mode: key` with key + a secondary identity path**: emit the key path, but include a README note that switching to identity is recommended.
- **Multiple LLM nodes with mixed auth**: instantiate one client per Executor's `__init__`. Don't share a single global client when the auth modes differ.
- **Placeholder secrets** (`<to-be-replaced>`, `${env:...}`): treat as the key path and surface the env var the customer must populate. Never paste the placeholder into source.
- **OpenAI (non-Azure)**: never emit `DefaultAzureCredential` — there is no identity option. Always key.
- **Confidence drop**: if the agent had to guess from env hints alone, emit a `# TODO(migration):` comment plus a short note in the README so the customer can confirm.
- **Custom-tool nodes that ignore the `connection` arg**: see [topics/custom-tool-nodes.md](custom-tool-nodes.md) — many internal gateways resolve credentials themselves from env. In that case the connection is decorative; pass `None` and document the real env vars the tool reads.

---

## Anti-patterns

- ❌ Emitting `api_key=os.environ["AZURE_OPENAI_API_KEY"]` when the source connection has `auth_mode: meid_token` — the customer doesn't have a key to set.
- ❌ Inventing a `Connection` class in MAF or wrapping env reads in something that imitates `pf.connections.get(...)`.
- ❌ Silently dropping a `CustomConnection`'s `configs`/`secrets` — they encode real configuration the tool relies on.
- ❌ Hard-coding endpoint / model values that came from a PF connection. Always route through env vars so the customer can override per environment.
- ❌ Asking the user "is this key or identity?" before checking the YAML / `pf connection show` / env files.

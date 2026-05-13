# Replacing Prompt Flow Connections

Prompt Flow connections (`AzureOpenAIConnection`, `OpenAIConnection`,
`CognitiveSearchConnection`, `CustomConnection`, etc.) are **no longer
supported** for migrated Microsoft Agent Framework workflows. Prompt Flow itself
is being retired (feature freeze 20 April 2026, full retirement 20 April 2027),
so the connection registry it relied on is going away too.

This affects both places where connections are commonly used:

- SDK clients in migrated workflows, such as `FoundryChatClient` or Azure AI
    Search clients.
- Your own Python code that used to receive a Prompt Flow connection object,
    such as a tool function that read `connection.api_key`, `connection.configs`,
    or `connection.secrets`.

In migrated code, pass credentials and configuration explicitly. Pick one of
the alternatives below.

---

## 1. Identity-based authentication (recommended)

No secret to store, rotate, or leak. Use Microsoft Entra ID and grant the
right RBAC role to your user (local) or managed identity (production).

```python
import os

from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["FOUNDRY_MODEL"],
    credential=DefaultAzureCredential(),
)
```

`DefaultAzureCredential` works locally after `az login` and in Azure when the
hosting resource has a managed identity. Swap to `ManagedIdentityCredential()`
when you want to be explicit in production. See
[phase-4-migrate-ops/4b-deployment/managed_identity.md](./phase-4-migrate-ops/4b-deployment/managed_identity.md).

Required roles (assign to the user / managed identity):

| Service | Role |
|---|---|
| Azure OpenAI | `Cognitive Services OpenAI User` |
| Microsoft Foundry project | `Azure AI Developer` |
| Azure AI Search | `Search Index Data Reader` (+ `Search Service Contributor` if you create indexes) |

Docs:
- [DefaultAzureCredential overview](https://learn.microsoft.com/azure/developer/python/sdk/authentication/credential-chains#defaultazurecredential-overview)
- [Managed identities for Azure resources](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview)
- [Authenticate to Azure OpenAI with Entra ID](https://learn.microsoft.com/azure/ai-services/openai/how-to/managed-identity)

---

## 2. Workspace / project connections

If you already have connections in a Microsoft Foundry project or an Azure
ML workspace and want to keep them, read them at runtime instead of
re-creating them as PF objects.

```python
import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)
conn = project.connections.get(name="my-connection", include_credentials=True)

# Connection is a mapping-like object. Common fields include:
# conn.name, conn.type, conn.target, conn.credentials, conn.metadata
target = conn.target
credentials = conn.credentials

# Pass the values your code needs into the client or function of your choice.
```

Use this option when you want a short-term bridge from existing workspace or
project connections. For new production code, identity-based authentication is
usually cleaner.

Docs:
- [Foundry project connections](https://learn.microsoft.com/azure/ai-foundry/how-to/connections-add)
- [`azure-ai-projects` Python SDK](https://learn.microsoft.com/python/api/overview/azure/ai-projects-readme)
- [`ConnectionsOperations.get`](https://learn.microsoft.com/python/api/azure-ai-projects/azure.ai.projects.operations.connectionsoperations?view=azure-python#azure-ai-projects-operations-connectionsoperations-get)
- [Azure ML workspace connections](https://learn.microsoft.com/azure/machine-learning/how-to-connection)

---

## 3. Environment variables and `.env` files

Simplest path for local development and CI. The repo uses this for every
phase-2 sample — see [.env.example](./.env.example).

```bash
# .env  (do not commit)
FOUNDRY_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com
FOUNDRY_MODEL=gpt-4o
```

```python
import os
from dotenv import load_dotenv

load_dotenv()
endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
```

Docs:
- [`python-dotenv`](https://pypi.org/project/python-dotenv/)
- [App Service app settings](https://learn.microsoft.com/azure/app-service/configure-common#configure-app-settings)
- [Azure Container Apps environment variables](https://learn.microsoft.com/azure/container-apps/environment-variables)

> Keep `.env` in `.gitignore`. Use this for **non-secret** config; combine
> with option 1 or 4 for anything sensitive.

---

## 4. Azure Key Vault

When you must keep an API key (third-party model provider, legacy system),
store it in Key Vault and read it at startup.

```python
import os

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

kv = SecretClient(
    vault_url=os.environ["KEY_VAULT_URL"],
    credential=DefaultAzureCredential(),
)
api_key = kv.get_secret("openai-api-key").value
```

Docs:
- [Key Vault overview](https://learn.microsoft.com/azure/key-vault/general/overview)
- [`azure-keyvault-secrets` Python SDK](https://learn.microsoft.com/python/api/overview/azure/keyvault-secrets-readme)

If your app runs on App Service or Azure Functions, you can also expose a Key
Vault secret as an app setting and keep your Python code using
`os.environ["SETTING_NAME"]`. For Azure Container Apps, use Container Apps
secrets or environment variables.

---

## Migrating user code that used a connection

Old Prompt Flow tools often accepted a connection object directly:

```python
def call_service(question: str, connection) -> str:
    endpoint = connection.configs["endpoint"]
    api_key = connection.secrets["api_key"]
    return call_api(endpoint=endpoint, api_key=api_key, question=question)
```

In migrated code, make the inputs explicit. For non-secret config, read from
environment variables. For secrets, prefer identity-based authentication or read
from Key Vault.

```python
import os

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def load_service_settings() -> tuple[str, str]:
    endpoint = os.environ["SERVICE_ENDPOINT"]
    kv = SecretClient(
        vault_url=os.environ["KEY_VAULT_URL"],
        credential=DefaultAzureCredential(),
    )
    api_key = kv.get_secret("service-api-key").value
    return endpoint, api_key


def call_service(question: str) -> str:
    endpoint, api_key = load_service_settings()
    return call_api(endpoint=endpoint, api_key=api_key, question=question)
```

---

## Quick mapping

| Prompt Flow connection | Recommended replacement |
|---|---|
| `AzureOpenAIConnection` (key) | Option 1 (Entra ID) — fall back to Option 4 |
| `AzureOpenAIConnection` already in workspace/project | Option 2 |
| `OpenAIConnection` (third-party key) | Option 4 |
| `CognitiveSearchConnection` | Option 1 |
| `CustomConnection.configs` | Option 3 |
| `CustomConnection.secrets` | Option 4 |

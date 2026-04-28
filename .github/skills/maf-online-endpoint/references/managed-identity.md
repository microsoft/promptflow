# Using Managed Identity Instead of API Keys

For production deployments, use managed identity with `FoundryChatClient`.
This removes the need to store API keys in your online endpoint environment
variables entirely.

Azure ML managed online endpoints automatically have a **system-assigned
managed identity** — no extra step is needed to enable it.

This pattern follows the
[azureml-examples managed identity sample](https://github.com/Azure/azureml-examples/blob/main/sdk/python/endpoints/online/managed/managed-identities/online-endpoints-managed-identity-sai.ipynb).

## Step 1: Get the endpoint's managed identity principal ID

```bash
az ml online-endpoint show \
  --name maf-endpoint \
  --resource-group <your-rg> \
  --workspace-name <your-workspace> \
  --query identity.principal_id -o tsv
```

## Step 2: Grant the identity access to the Foundry project

```bash
az role assignment create \
  --role "Cognitive Services User" \
  --assignee-object-id <principal-id-from-step-1> \
  --assignee-principal-type ServicePrincipal \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-resource>
```

> **Note:** Use `Cognitive Services User` (not `Azure AI Developer`).
> The `Azure AI Developer` role does not include the
> `Microsoft.CognitiveServices/accounts/AIServices/agents/write` data action
> required by Foundry. Allow 5–10 minutes for RBAC data plane propagation.

## Step 3: Update your client code

Use `DefaultAzureCredential()` — it automatically selects managed identity
when running in Azure and Azure CLI credentials locally:

```python
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["FOUNDRY_MODEL"],
    credential=DefaultAzureCredential(),
)
agent = Agent(client=client, name="MyAgent", instructions="...")
```

For explicit managed identity in production-only code:

```python
from azure.identity import ManagedIdentityCredential

client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["FOUNDRY_MODEL"],
    credential=ManagedIdentityCredential(),
)
```

## Python SDK — Programmatic RBAC Assignment

Following the managed identity sample, you can assign roles programmatically:

```python
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.authorization.models import RoleAssignmentCreateParameters
from azure.identity import AzureCliCredential
import uuid

credential = AzureCliCredential()

# Get endpoint identity
endpoint = ml_client.online_endpoints.get("maf-endpoint")
principal_id = endpoint.identity.principal_id

# Create authorization client
auth_client = AuthorizationManagementClient(
    credential=credential,
    subscription_id=subscription_id,
    api_version="2020-10-01-preview",
)

# Find Cognitive Services User role
scope = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.CognitiveServices/accounts/{foundry_account}"
role_defs = auth_client.role_definitions.list(scope=scope)
role_def = next(r for r in role_defs if r.role_name == "Cognitive Services User")

# Assign
auth_client.role_assignments.create(
    scope=scope,
    role_assignment_name=str(uuid.uuid4()),
    parameters=RoleAssignmentCreateParameters(
        role_definition_id=role_def.id,
        principal_id=principal_id,
    ),
)
```

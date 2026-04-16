# Using Managed Identity Instead of API Keys

For production deployments, use managed identity with `FoundryChatClient`.
This removes the need to store API keys in your online endpoint environment
variables entirely.

Azure ML managed online endpoints automatically have a **system-assigned
managed identity** — no extra step is needed to enable it.

## Step 1: Get the endpoint's managed identity principal ID

    az ml online-endpoint show \
      --name maf-endpoint \
      --resource-group <your-rg> \
      --workspace-name <your-workspace> \
      --query identity.principal_id -o tsv

## Step 2: Grant the identity access to the Foundry project

    az role assignment create \
      --role "Cognitive Services User" \
      --assignee-object-id <principal-id-from-step-1> \
      --assignee-principal-type ServicePrincipal \
      --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-resource>

> **Note:** Use `Cognitive Services User` (not `Azure AI Developer`).
> The `Azure AI Developer` role does not include the
> `Microsoft.CognitiveServices/accounts/AIServices/agents/write` data action
> required by Foundry. Allow 5–10 minutes for RBAC data plane propagation.

## Step 3: Update your client code

Use `ManagedIdentityCredential()` as the credential:

    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient
    from azure.identity import ManagedIdentityCredential

    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["FOUNDRY_MODEL"],
        credential=ManagedIdentityCredential(),
    )
    agent = Agent(client=client, name="MyAgent", instructions="...")

## Step 4: Verify

`DefaultAzureCredential` also works and will automatically use managed
identity when running in Azure, and Azure CLI credentials when running locally —
making it a good choice for code that needs to work in both environments.

# Using Managed Identity Instead of API Keys

For production deployments, use managed identity with `FoundryChatClient`.
This removes the need to store API keys in your Container App environment
variables entirely.

## Step 1: Enable managed identity on the Container App

    az containerapp identity assign \
      --name maf-app \
      --resource-group <your-rg> \
      --system-assigned

## Step 2: Grant the identity access to the Foundry project

    az role assignment create \
      --role "Cognitive Services OpenAI User" \
      --assignee <principal-id-from-step-1> \
      --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-resource>

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

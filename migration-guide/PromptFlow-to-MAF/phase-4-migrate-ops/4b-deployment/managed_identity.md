# Using Managed Identity Instead of API Keys

For production deployments, replace static API keys with managed identity.
This removes the need to store `AZURE_OPENAI_API_KEY` in your Container App
environment variables entirely.

## Step 1: Enable managed identity on the Container App

    az containerapp identity assign \
      --name maf-app \
      --resource-group <your-rg> \
      --system-assigned

## Step 2: Grant the identity access to Azure OpenAI

    az role assignment create \
      --role "Cognitive Services OpenAI User" \
      --assignee <principal-id-from-step-1> \
      --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<openai-resource>

## Step 3: Update your client code

Replace `AzureOpenAIChatClient()` (which reads the API key from environment)
with an explicit credential:

    from agent_framework.azure import AzureOpenAIChatClient
    from azure.identity import ManagedIdentityCredential

    client = AzureOpenAIChatClient(
        credential=ManagedIdentityCredential()
    )

## Step 4: Remove the API key from your Container App env vars

    az containerapp update \
      --name maf-app \
      --resource-group <your-rg> \
      --remove-env-vars AZURE_OPENAI_API_KEY

`DefaultAzureCredential` also works and will automatically use managed
identity when running in Azure, and Azure CLI credentials when running locally —
making it a good choice for code that needs to work in both environments.

# Promptflow Secret Setup

## Prerequisites
``` bash
# Login to the az cli
az login
az account set -s <subscription-id>
```

## AzureML Connections
A Custom Connection is a generic connection type that stores and manages credentials required for interacting with LLMs. It has two dictionaries, `secrets` for secrets to be stored in Key Vault, and `configs` for non-secrets that are stored in the AzureML workspace.


You can create a custom connection in the AzureML workspace by following the instructions [here](https://learn.microsoft.com/en-us/azure/machine-learning/prompt-flow/tools-reference/python-tool?view=azureml-api-2#create-a-custom-connection). The key-value pairs required are listed in the Secrets and Configs sections.

The following variables are required to be set as secret:
- AZURE_SEARCH_ADMIN_KEY
- OPENAI_API_KEY
- AML_SUBSCRIPTION_ID
- AML_RESOURCE_GROUP_NAME
- AML_WORKSPACE_NAME

And the remaining variables must not be set as secret:
- AZURE_SEARCH_SERVICE_ENDPOINT
- OPENAI_ENDPOINT
- OPENAI_API_VERSION

The following variables are optional:
- AZURE_LANGUAGE_SERVICE_KEY - secret
- AZURE_LANGUAGE_SERVICE_ENDPOINT - non secret
- LOGGING_LEVEL - non secret

## Configuring your connection locally 
To configure promptflow to connect to AzureML, create a file `./azureml/config.json` and update it with the `workspace_name`, `resource_group`, and `subscription_id` that your connection is stored in. You can find more information about this in the [documentation](https://microsoft.github.io/promptflow/how-to-guides/set-global-configs.html#azureml).

To update the local promptflow connection provider to look for AzureML connections, you can use the following code:
``` bash
# Set your promptflow connection provider to azureml
pf config set connection.provider=azureml

# Verify that the connection appears
pf connection list
```
Note: Depending on the context you're running the `pf` commands from, you may need to move the `.azureml` folder into the root of the repository. The extension can look in a different location than when running with the cli, so you may need the file in both the root and the rag-experiment-accelerator directory.

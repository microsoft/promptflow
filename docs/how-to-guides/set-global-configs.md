# Set global configs
Promptflow supports setting global configs to avoid passing the same parameters to each command. The global configs are stored in a yaml file, which is located at ~/.promptflow/pf.yaml by default.

The config file is shared between promptflow extension and sdk/cli. Promptflow extension controls each config through UI, so the following sections will show how to set global configs using promptflow cli.

## Set config
```shell
pf config set <config_name>=<config_value>
```
For example:
```shell
pf config set connection.provider="azureml:/subscriptions/<your-subscription>/resourceGroups/<your-resourcegroup>/providers/Microsoft.MachineLearningServices/workspaces/<your-workspace>"
```

## Show config
The following command will get all configs and show them as json format:
```shell
pf config show
```
After running the above config set command, show command will return the following result:
```json
{
  "connection": {
    "provider": "azureml:/subscriptions/<your-subscription>/resourceGroups/<your-resourcegroup>/providers/Microsoft.MachineLearningServices/workspaces/<your-workspace>"
  }
}
```

## Supported configs
### connection.provider
The connection provider, default to "local". There are 3 possible provider values.
#### local
Set connection provider to local with `connection.provider=local`.

Connections will be saved locally. `PFClient`(or `pf connection` commands) will [manage local connections](manage-connections.md). Consequently, the flow will be executed using these local connections.
#### full azure machine learning workspace resource id
Set connection provider to a specific workspace with:
```
connection.provider=azureml:/subscriptions/<your-subscription>/resourceGroups/<your-resourcegroup>/providers/Microsoft.MachineLearningServices/workspaces/<your-workspace>
```

When `get` or `list` connections, `PFClient`(or `pf connection` commands) will return workspace connections, and flow will be executed using these workspace connections.
_Secrets for workspace connection will not be shown by those commands, which means you may see empty dict `{}` for custom conenctions._

Note that `create`, `update` and `delete` commands are not supported for workspace connections, please manage it in workspace portal, az ml cli or AzureML SDK. 

#### azureml
In addition to the full resource id, you can designate the connection provider as "azureml" with `connection.provider=azureml`. In this case,
promptflow will attempt to retrieve the workspace configuration by searching `.azureml/config.json` from the current directory,  then progressively from its parent folders. So it's possible to set the workspace configuration for different flow by placing the config file in the project folder.

The expected format of the config file is as follows:
```json
{
  "workspace_name": "<your-workspace-name>",
  "resource_group": "<your-resource-group>",
  "subscription_id": "<your-subscription-id>"
}
```
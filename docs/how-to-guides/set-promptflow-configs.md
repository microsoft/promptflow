# Set promptflow configs
:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](faq.md#stable-vs-experimental).
:::

Promptflow supports setting global configs to avoid passing the same parameters to each command. The global configs are stored in a yaml file, which is located at `~/.promptflow/pf.yaml` by default.

Additionally, promptflow supports setting configs to a specified path, and these configs will only take effect for the Promptflow program when the working directory is the specified path or its subdirectories.
The configs are stored in a yaml file, which is located at `<config_folder>/pf.yaml`.

The config file is shared between promptflow extension and sdk/cli. Promptflow extension controls each config through UI, so the following sections will show how to set global configs using promptflow cli.

## Set config
Set global config
```shell
pf config set <config_name>=<config_value>
```
For example:
```shell
pf config set connection.provider="azureml://subscriptions/<your-subscription>/resourceGroups/<your-resourcegroup>/providers/Microsoft.MachineLearningServices/workspaces/<your-workspace>"
```

Setting the config for a specific path
```shell
pf config set <config_name>=<config_value> --path <config_folder>
```
For example:
```shell
pf config set connection.provider="azureml://subscriptions/<your-subscription>/resourceGroups/<your-resourcegroup>/providers/Microsoft.MachineLearningServices/workspaces/<your-workspace>" --path .
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
    "provider": "azureml://subscriptions/<your-subscription>/resourceGroups/<your-resourcegroup>/providers/Microsoft.MachineLearningServices/workspaces/<your-workspace>"
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
connection.provider=azureml://subscriptions/<your-subscription>/resourceGroups/<your-resourcegroup>/providers/Microsoft.MachineLearningServices/workspaces/<your-workspace>
```

When `get` or `list` connections, `PFClient`(or `pf connection` commands) will return workspace connections, and flow will be executed using these workspace connections.
_Secrets for workspace connection will not be shown by those commands, which means you may see empty dict `{}` for custom connections._

:::{note}
Command `create`, `update` and `delete` are not supported for workspace connections, please manage it in workspace portal, [Azure AI Studio](https://learn.microsoft.com/en-us/azure/ai-studio/how-to/connections-add), az ml cli or azure-ai-ml sdk.
:::
 

#### azureml
In addition to the full resource id, you can designate the connection provider as "azureml" with `connection.provider=azureml`. In this case,
promptflow will attempt to retrieve the workspace configuration by searching `.azureml/config.json` from the current directory, then progressively from its parent folders. So it's possible to set the workspace configuration for different flow by placing the config file in the project folder.

The expected format of the config file is as follows:
```json
{
  "workspace_name": "<your-workspace-name>",
  "resource_group": "<your-resource-group>",
  "subscription_id": "<your-subscription-id>"
}

```
### service.host
The promptflow service host, default to "127.0.0.1". You can set the service host with `service.host=<your-host>`.

For example:
```shell
pf config set service.host="0.0.0.0"
```

> 💡 Tips
> In addition to the CLI command line setting approach, we also support setting this connection provider through the VS Code extension UI. [Click here to learn more](../cloud/azureai/consume-connections-from-azure-ai.md).
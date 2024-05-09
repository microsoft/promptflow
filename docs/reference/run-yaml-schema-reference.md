# Run YAML Schema

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../how-to-guides/faq.md#stable-vs-experimental).
:::

The source JSON schema can be found at [Run.schema.json](https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json)

## YAML syntax

| Key                     | Type          | Description                                                                                                                                                                                                                                                             |
|-------------------------|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `$schema`               | string        | The YAML schema. If you use the prompt flow VS Code extension to author the YAML file, including $schema at the top of your file enables you to invoke schema and resource completions.                                                                                 |
| `name`                  | string        | The name of the run.                                                                                                                                                                                                                                                    |
| `flow`                  | string        | Path of the flow directory.                                                                                                                                                                                                                                             |
| `description`           | string        | Description of the run.                                                                                                                                                                                                                                                 |
| `display_name`          | string        | Display name of the run.                                                                                                                                                                                                                                                |
| `data`                  | string        | Input data for the run. Local path or remote uri(starts with azureml: or public URL) are supported. Note: remote uri is only supported for cloud run.                                                                                                                   |
| `run`                   | string        | Referenced flow run name. For example, you can run an evaluation flow against an existing run.                                                                                                                                                                          |
| `column_mapping`        | object        | Inputs column mapping, use `${data.xx}` to refer to data columns, use `${run.inputs.xx}` to refer to referenced run's data columns, and `${run.outputs.xx}` to refer to run outputs columns.                                                                            |
| `connections`           | object        | Overwrite node level connections with provided value. Example: --connections node1.connection=test_llm_connection node1.deployment_name=gpt-35-turbo                                                                                                                    |
| `environment_variables` | object/string | Environment variables to set by specifying a property path and value. Example: `{"key1"="${my_connection.api_key}"}`. The value reference to connection keys will be resolved to the actual value, and all environment variables specified will be set into os.environ. |
| `properties`            | object        | Dictionary of properties of the run.                                                                                                                                                                                                                                    |
| `tags`                  | object        | Dictionary of tags of the run.                                                                                                                                                                                                                                          |
| `resources`             | object        | Dictionary of resources used for compute session. Only supported for cloud run. See [Resources Schema](#resources-schema) for the set of configurable properties.                                                                                                     |
| `variant`               | string        | The variant for the run.                                                                                                                                                                                                                                                |
| `status`                | string        | The status of the run. Only available for when getting an existing run. Won't take affect if set when creating a run.                                                                                                                                                   |
|`identity`| object | Dictionary of identity configuration for compute session. Only supported for cloud run. See [Identity Schema](#identity-schema) for the set of configurable properties.


### Resources Schema

| Key             | Type   | Description                                         |
|-----------------|--------|-----------------------------------------------------|
| `instance_type` | string | The instance type for compute session of the run. |
| `compute`       | string | The compute instance for compute session session. |


### Identity Schema

| Key         | Type   | Description                                                          |
|-------------|--------|----------------------------------------------------------------------|
| `type`      | string | Identity type, currently only support `managed` and `user_identity`. |
| `client_id` | string | Client id for managed identity, only avaible on managed identity.    |

## Examples

Run examples are available in the [GitHub repository](https://github.com/microsoft/promptflow/tree/main/examples/flows).

- [basic](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/basic/run.yml)
- [web-classification](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification/run.yml)
- [flow-with-additional-includes](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/flow-with-additional-includes/run.yml)

### Run with identity examples

```yaml
# default value
identity:
  type: user_identity

# use workspace primary UAI
identity:
  type: managed

# use specified client_id's UAI
identity:
  type: managed
  client_id: xxx
```

# Run YAML Schema

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../how-to-guides/faq.md#stable-vs-experimental).
:::

The source JSON schema can be found at [Run.schema.json](https://azuremlschemas.azureedge.net/promptflow/latest/Run.schema.json)

## YAML syntax

| Key                     | Type          | Description                                                                                                                                                                                                                                                             |
|-------------------------|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `$schema`               | string        | The YAML schema. If you use the Prompt flow VS Code extension to author the YAML file, including $schema at the top of your file enables you to invoke schema and resource completions.                                                                                 |
| `name`                  | string        | The name of the run.                                                                                                                                                                                                                                                    |
| `flow`                  | string        | Path of the flow directory.                                                                                                                                                                                                                                             |
| `description`           | string        | Description of the run.                                                                                                                                                                                                                                                 |
| `display_name`          | string        | Display name of the run.                                                                                                                                                                                                                                                |
| `runtime`               | string        | The runtime for the run. Only supported for cloud run. run.                                                                                                                                                                                                             |
| `data`                  | string        | Input data for the run. Local path or remote uri(starts with azureml: or public URL) are supported. Note: remote uri is only supported for cloud run.                                                                                                                   |
| `run`                   | string        | Referenced flow run name. For example, you can run an evaluation flow against an existing run.                                                                                                                                                                          |
| `column_mapping`        | object        | Inputs column mapping, use ${data.xx} to refer to data file columns, use ${run.inputs.xx} and ${run.outputs.xx} to refer to run inputs/outputs columns.                                                                                                                 |
| `connections`           | object        | Overwrite node level connections with provided value. Example: --connections node1.connection=test_llm_connection node1.deployment_name=gpt-35-turbo                                                                                                                    |
| `environment_variables` | object/string | Environment variables to set by specifying a property path and value. Example: `{"key1"="${my_connection.api_key}"}`. The value reference to connection keys will be resolved to the actual value, and all environment variables specified will be set into os.environ. |
| `properties`            | object        | Dictionary of properties of the run.                                                                                                                                                                                                                                    |
| `tags`                  | object        | Dictionary of tags of the run.                                                                                                                                                                                                                                          |
| `resources`             | object        | Dictionary of resources used for automatic runtime. Only supported for cloud run. See [Resources Schema](#resources-schema) for the set of configurable properties.                                                                                                     |
| `variant`               | string        | The variant for the run.                                                                                                                                                                                                                                                |
| `status`                | string        | The status of the run. Only available for when getting an existing run. Won't take affect if set when creating a run.                                                                                                                                                   |

### Resources Schema  

| Key                                 | Type    | Description                                                 |
|-------------------------------------|---------|-------------------------------------------------------------|
| `instance_type`                     | string  | The instance type for automatic runtime of the run.         |
| `idle_time_before_shutdown_minutes` | integer | The idle time before automatic runtime shutdown in minutes. |

## Examples

Run examples are available in the [GitHub repository](https://github.com/microsoft/promptflow/tree/main/examples/flows).

- [basic](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/basic/run.yml)
- [web-classification](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification/run.yml)
- [flow-with-additional-includes](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/flow-with-additional-includes/run.yml)

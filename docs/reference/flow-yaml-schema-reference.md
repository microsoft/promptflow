# Flow YAML Schema

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../how-to-guides/faq.md#stable-vs-experimental).
:::

The source JSON schema can be found at [Flow.schema.json](https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json)

## YAML syntax

| Key                        | Type      | Description                                                                                                                                                                                                       |
|----------------------------|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `$schema`                  | string    | The YAML schema. If you use the Prompt flow VS Code extension to author the YAML file, including `$schema` at the top of your file enables you to invoke schema and resource completions.              |
| `inputs`                   | object    | Dictionary of flow inputs. The key is a name for the input within the context of the flow and the value is the flow input definition.                                                                             |
| `inputs.<input_name>`      | object    | The flow input definition. See [Flow input](#flow-input) for the set of configurable properties.                                                                                                                  |
| `outputs`                  | object    | Dictionary of flow outputs. The key is a name for the output within the context of the flow and the value is the flow output definition.                                                                          |
| `outputs.<output_name>`    | object    | The component output definition. See [Flow output](#flow-output) for the set of configurable properties.                                                                                                          |
| `nodes`                    | array     | Sets of dictionary of individual nodes to run as steps within the flow. Node can use built-in tool or third-party tool. See [Nodes](#nodes) for more information.                                                 |
| `node_variants`            | object    | Dictionary of nodes with variants. The key is the node name and value contains variants definition and `default_variant_id`. See [Node variants](#node-variants) for more information.                            |
| `environment`              | object    | The environment to use for the flow. The key can be `image` or `python_requirements_txt` and the value can be either a image or a python requirements text file.                                                  |
| `additional_includes`      | array     | Additional includes is a list of files that can be shared among flows. Users can specify additional files and folders used by flow, and Prompt flow will help copy them all to the snapshot during flow creation. |


### Flow input

| Key               | Type                                      | Description                                          | Allowed values                                      |
|-------------------|-------------------------------------------|------------------------------------------------------|-----------------------------------------------------|
| `type`            | string                                    | The type of flow input.                              | `int`, `double`, `bool`, `string`, `list`, `object` |
| `description`     | string                                    | Description of the input.                            |                                                     |
| `default`         | int, double, bool, string, list or object | The default value for the input.                     |                                                     |
| `is_chat_input`   | boolean                                   | Whether the input is the chat flow input.            |                                                     |
| `is_chat_history` | boolean                                   | Whether the input is the chat history for chat flow. |                                                     |

### Flow output

| Key              | Type    | Description                                                                   | Allowed values                                      |
|------------------|---------|-------------------------------------------------------------------------------|-----------------------------------------------------|
| `type`           | string  | The type of flow output.                                                      | `int`, `double`, `bool`, `string`, `list`, `object` |
| `description`    | string  | Description of the output.                                                    |                                                     |
| `reference`      | string  | A reference to the node output, e.g. ${<node_name>.output.<node_output_name>} |                                                     |
| `is_chat_output` | boolean | Whether the output is the chat flow output.                                   |                                                     |

### Nodes
Nodes is a set of node which is a dictionary with following fields. Below, we only show the common fields of a single node using built-in tool.

| Key            | Type   | Description                                                                                                                                                                                                                                               | Allowed values                                                                                       |
|----------------|--------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| `name`         | string | The name of the node.                                                                                                                                                                                                                                     |                                                                                                      |
| `type`         | string | The type of the node.                                                                                                                                                                                                                                     | Type of built-in tool like `Python`, `Prompt`, `LLM` and third-party tool like `Vector Search`, etc. |
| `inputs`       | object | Dictionary of node inputs. The key is the input name and the value can be primitive value or a reference to the flow input or the node output, e.g. `${inputs.<flow_input_name>}`, `${<node_name>.output}` or `${<node_name>.output.<node_output_name>}`  |                                                                                                      |
| `source`       | object | Dictionary of tool source used by the node. The key contains `type`, `path` and `tool`. The type can be `code`, `package` and `package_with_prompt`.                                                                                                      |                                                                                                      |
| `provider`     | string | It indicates the provider of the tool. Used when the `type` is LLM.                                                                                                                                                                                       | `AzureOpenAI` or `OpenAI`                                                                            |
| `connection`   | string | The connection name which has been created before. Used when the `type` is LLM.                                                                                                                                                                           |                                                                                                      |
| `api`          | string | The api name of the provider. Used when the `type` is LLM.                                                                                                                                                                                                |                                                                                                      |
| `module`       | string | The module name of the tool using by the node. Used when the `type` is LLM.                                                                                                                                                                               |                                                                                                      |
| `use_variants` | bool   | Whether the node has variants.                                                                                                                                                                                                                            |                                                                                                      |


### Node variants
Node variants is a dictionary containing variants definition for nodes with variants with their respective node names as dictionary keys.
Below, we explore the variants for a single node.

| Key                  | Type     | Description                                                                                                                                                                                                                                                                                                   | Allowed values |
|----------------------|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| `<node_name>`        | string   | The name of the node.                                                                                                                                                                                                                                                                                         |                |
| `default_variant_id` | string   | Default variant id.                                                                                                                                                                                                                                                                                           |                |
| `variants `          | object   | This dictionary contains all node variations, with the variant id serving as the key and a node definition dictionary as the corresponding value.  Within the node definition dictionary, the key labeled 'node' should contain a variant definition similar to [Nodes](#nodes), excluding the 'name' field.  |                |



## Examples

Flow examples are available in the [GitHub repository](https://github.com/microsoft/promptflow/tree/main/examples/flows).

- [basic](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/basic)
- [web-classification](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/web-classification)
- [basic-chat](https://github.com/microsoft/promptflow/tree/main/examples/flows/chat/basic-chat)
- [chat-with-pdf](https://github.com/microsoft/promptflow/tree/main/examples/flows/chat/chat-with-pdf)
- [eval-basic](https://github.com/microsoft/promptflow/tree/main/examples/flows/evaluation/eval-basic)
# Class based flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

When user need to persist objects (like connection) in memory during multiple rounds of flow runs, they can write a callable class as flow entry and put persist params in `__init__` method.

If user need to log metrics on batch run outputs, they can add an `__aggregate__` method and it will be scheduled after batch run finishes.
The `__aggregate__` method should only contain 1 params which is list of batch run results.

See [connection support](#connection-support) & [aggregation support](#aggregation-support) for more details.

## Class as a flow

Assume we have a file `flow_entry.py`:

```python
class Reply(TypedDict):
    output: str

class MyFlow:
    def __init__(self, model_config: AzureOpenAIModelConfiguration, flow_config: dict):
      """Flow initialization logic goes here."""
      self.model_config = model_config
      self.flow_config = flow_config

    def __call__(question: str) -> Reply:
      """Flow execution logic goes here."""
      return Reply(output=output)

    def __aggregate__(self, line_results: List[str]) -> dict:
      """Aggregation logic goes here. Return key-value pair as metrics."""
      return {"key": val}
```


## Flow test

Since flow's definition is function/callable class. We recommend user directly run it like running other scripts:

```python
class MyFlow:
    pass
if __name__ == "__main__":
    flow = MyFlow(model_config, flow_config)
    output = flow(question)
    metrics = flow.__aggregate__([output])
    # check metrics here
```

You can also test the flow using CLI:
```bash
# flow entry syntax: path.to.module:ClassName
pf flow test --flow flow_entry:MyFlow --inputs question="What's the capital of France?" --init init.json
```

Check out a full example here: [basic-chat](https://github.com/microsoft/promptflow/tree/main/examples/flex-flows/basic-chat)

### Chat with a flow

Chat with flow in CLI is supported:

```bash
pf flow test --flow flow_entry:MyFlow --inputs inputs.json --init init.json --ui
```

Check [here](../chat-with-a-flow/index.md) for more information.

## Batch run

User can also batch run a flow.

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
pf run create --flow "path.to.module:ClassName" --data "./data.jsonl"
```

:::

:::{tab-item} SDK
:sync: SDK
```python
# user can also directly use entry in `flow` param for batch run
pf.run(flow="path.to.module:ClassName", init="./init.jsonl", data="./data.jsonl")
```

:::
::::

Or directly run the imported flow class or flow instance.

```python
class MyFlow:
    pass
pf.run(flow=MyFlow, init={"model_config": config, "flow_config": {}}, data="./data.jsonl")
# or
flow_obj = MyFlow(model_config=config, flow_config={})
pf.run(flow=flow_obj, data="./data.jsonl")
```

Learn more on this topic on [Run and evaluate a flow](../run-and-evaluate-a-flow/index.md)

## YAML support

User can write a YAML file with name `flow.flex.yaml` manually or save a function/callable entry to YAML file.
A flow YAML may look like this:

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json
entry: path.to.module:ClassName
```

## Batch run with YAML

User can batch run a flow. Flow init function's param is supported by `init` parameter.

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

User need to write an JSON file as init's value since it's hard to write model config in command line.

```json
{
    "model_config": {
        "azure_endpoint": "my_endpoint",
        "azure_deployment": "my_deployment",
        "api_key": "actual_api_key"
    },
    "flow_config": {}
}
```

```bash
pf run create --flow "./flow.flex.yaml" --data "./data.jsonl" --init init.json
```

:::

:::{tab-item} SDK
:sync: SDK

```python
pf = PFClient()

config = AzureOpenAIModelConfiguration(
  azure_deployment="my_deployment",
  api_key="actual_key"
)
# if init's value is not json serializable, raise user error
pf.run(flow="./flow.flex.yaml", init={"model_config": config, "flow_config": {}}, data="./data.jsonl")

# when submit to cloud, user can only use connection
# in runtime executor will resolve connection in AzureOpenAIModelConfiguration and set connection's fields to ModelConfig: equal to original ModelConfiguration.from_connection()
config = AzureOpenAIModelConfiguration(
  azure_deployment="my_embedding_deployment",
  connection="my-aoai-connection",
) 
pfazure.run(flow="./flow.flex.yaml", init={"model_config": config, "flow_config": {}}, data="./data.jsonl")
```

:::
::::

## Deploy a flow

User can serve a flow. Flow init function's param is supported by `init` parameter.
The flow should have complete init/inputs/outputs specification in YAML to make sure serving swagger can be generated.

User need to write an JSON file as init's value since it's hard to write model config in command line.

```json
{
    "model_config": {
        "azure_endpoint": "my_endpoint",
        "azure_deployment": "my_deployment",
        "api_key": "actual_api_key"
    },
    "flow_config": {}
}
```

```bash
# user can only pass model config by file 
pf flow serve --source "./"  --port 8088 --host localhost --init path/to/init.json
```

Learn more: [Deploy a flow](../deploy-a-flow/index.md).

## Connection support

### Model config in `__init__`

Just like example in [batch run](#batch-run-with-yaml), it's supported to reference connection in ModelConfig.
And connection will be resolved and flatten connection's fields to ModelConfig.

### Connection in `__init__`

It's also supported to directly pass connection by **name** in `__init__`. 

```python
class MyFlow:
    def __init__(self, my_connection: AzureOpenAIConnection):
        pass
```

Note:

- Union of connection types(`Union[OpenAIConnection, AzureOpenAIConnection]`) is not supported.

#### Batch run with connection

User can pass connection name to connection field in `init`.

In local, the connection name will be replaced with local connection object in execution time.
In cloud, the connection name will be replaced with workspace's connection object in execution time.

```python
# local connection "my_connection"'s instance will be passed to `__init__`
pf.run(flow="./flow.flex.yaml", init={"connection": "my_connection"}, data="./data.jsonl")
# cloud connection "my_cloud_connection"'s instance will be passed to `__init__`
pfazure.run(flow="./flow.flex.yaml", init={"connection": "my_cloud_connection"}, data="./data.jsonl")
```

### Environment variable connections(EVC)

If flow YAML has `environment_variables` and it's value is a connection reference like this:

```yaml
environment_variables:
  AZURE_OPENAI_API_KEY: ${open_ai_connection.api_key}
  AZURE_OPENAI_ENDPOINT: ${open_ai_connection.api_base}
```

The environment variable's value will be resolved to actual value in runtime.
If the connection not exist (in local or cloud), connection not found error will be raised.

**Note**: User can override the `environment_variables` with existing environment variable keys in `flow.flex.yaml`:

```bash
pf run create --flow . --data ./data.jsonl --environment-variables AZURE_OPENAI_API_KEY='${new_connection.api_key}' AZURE_OPENAI_ENDPOINT='my_endpoint'
```

Overriding with environment variable names which not exist in `flow.flex.yaml` is not supported.
Which means if user added environment variables which does not exist in `flow.flex.yaml` in runtime, it's value won't be resolved.

For example,

```bash
pf run create --flow . --data ./data.jsonl --environment-variables NEW_API_KEY='${my_new_connection.api_key}'
```

The `NEW_API_KEY`'s value won't be resolved to connection's API key.

## Aggregation support

Aggregation support is introduce to help user calculate metrics.

```python
class MyFlow:
    def __call__(text: str) -> str:
      """Flow execution logic goes here."""
      pass

    # will only execute once after batch run finished.
    # the processed_results will be list of __call__'s output and we will log the return value as metrics automatically.
    def __aggregate__(self, processed_results: List[str]) -> dict:
        for element in processed_results:
            # If __call__'s output is primitive type, element will be primitive type.
            # If __call__'s output is dataclass, element will be a dictionary, but can access it's attribute with `element.attribute_name`
            # For other cases, it's recommended to access by key `element["attribute_name"]`

```

**Note**:

There's several limitations on aggregation support:

- The aggregation function will only execute in batch run.
- Only 1 hard coded `__aggregate__` function is supported.
- The `__aggregate__` will only be passed **1** positional arguments when executing.
- The aggregation function’s input will be flow run’s outputs list.
  - Each element inside `processed_results` passed passed inside `__aggregate__` function is not same object with each line's `__call__` returns.
  - The reconstructed element is a dictionary which supports 1 layer attribute access. But it's recommended to access them by key. See the above example for usage.
- If aggregation function accept more than 1 arguments, raise error in submission phase.

## Next steps

- [Input output format](./input-output-format.md)
- [Class based flow sample](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/chat-basic/README.md)
- [Class based flow evaluation sample](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/eval-code-quality/README.md)

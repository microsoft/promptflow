# Class based flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

When user need to persist objects (like connection) in memory during multiple rounds of flow runs, they can write a callable class as flex flow's entry and put persist params in `__init__` method.

If user need to log metrics on batch run outputs, they can add an `__aggregate__` method and it will be scheduled after batch run finishes.
The `__aggregate__` method should only contain 1 params which is list of batch run results.

See [connection support](#connection-support) & [aggregation support](#aggregation-support-metrics) for more details.

## Authoring

```python
class Reply(TypedDict):
    output: str

class MyFlow:
    def __init__(self, model_config: AzureOpenAIModelConfiguration, flow_config: dict):
      """Flow initialization logic goes here."""
      self.model_config = model_config
      self.flow_config = flow_config

    def __call__(text: str) -> Reply:
      """Flow execution logic goes here."""
      return Reply(output=output)

    def __aggregate__(self, line_results: List[str]) -> dict:
      """Aggregation logic goes here. Return key-value pair as metrics."""
      return {"key": val}
```

## YAML support

Similar as DAG flow. YAML file is identifier for flex flow.
Flex flow will use `flow.flex.yaml` as it's identifier.
User can write the YAML file manually or save a function/callable entry to YAML file.
A flex flow YAML may look like this:

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json
entry: path.to.module:ClassName
```

## Flow test

Since flex flow's definition is function/callable class. We recommend user directly run it like running other scripts:

```python
class MyFlow:
    pass
if __name__ == "__main__":
    flow = MyFlow(**init_args)
    output = flow(**call_args)
    metrics = flow.__aggregate__([output])
    # check metrics here
```

## Chat with a flow

Chat with flex flow in CLI is supported:

```bash
pf flow test --flow path/to/flow --inputs path/to/inputs --init path/to/init --ui
```

Check [here](../chat-with-a-flow) for more information.

## Batch run

User can batch run a flex flow. Flow init function's param is supported by `init` parameter.

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

## Batch run without YAML

User can also batch run a flex flow without YAML.
Instead of calling `pf.save` to create flow YAML first.

```python
# user can also directly use entry in `flow` param for batch run
pf.run(flow="path.to.module:ClassName", data="./data.jsonl")
```

Or directly run the imported flow class or flow instance.
**Note**: this only works in local.

```python
class MyFlow:
    pass
pf.run(flow=MyFlow, init={"model_config": config, "flow_config": {}}, data="./data.jsonl")
# or
flow_obj = MyFlow(model_config=config, flow_config={})
pf.run(flow=flow_obj, data="./data.jsonl")
```

## Serve

User can serve a flex flow. Flow init function's param is supported by `init` parameter.
The flex flow should have complete init/inputs/outputs specification in YAML to make sure serving swagger can be generated.

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

## Build & deploy

Build & deploy a flex flow is supported like [DAG flow](../deploy-a-flow/).

## Connection support

### Model config in `__init__`

Just like example in [batch run](#batch-run), it's supported to reference connection in ModelConfig.
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

If flex flow's YAML has `environment_variables` and it's value is a connection reference like this:

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

## Aggregation support (metrics)

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

- Referencing node outputs is not supported (there’s no node concept in flex flow).
- The aggregation function will only execute in batch run.
- Only 1 hard coded `__aggregate__` function is supported.
- The `__aggregate__` will only be passed **1** positional arguments when executing.
- The aggregation function’s input will be flow run’s outputs list.
  - Each element inside `processed_results` passed passed inside `__aggregate__` function is not same object with each line's `__call__` returns.
  - The reconstructed element is a dictionary which supports 1 layer attribute access. But it's recommended to access them by key. See the above example for usage.
- If aggregation function accept more than 1 arguments, raise error in submission phase.

## Next steps

- [Supported types](./supported-types.md)
- [Class based flex flow sample](../../../examples/flex-flows/chat-basic/)
- [Class based flex flow evaluation sample](../../../examples/flex-flows/eval-code-quality/)

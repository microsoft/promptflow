# Class based flow

When user need to persist objects(like connection) in memory during multiple rounds of flow runs.
They can write a callable class as flex flow's entry and put persist params in `__init__` method.

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
A complete flex flow YAML may look like this:

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json
entry: path.to.module:ClassName
inputs:
  text:
    type: string
outputs:
  output:
    type: string
init:
  model_config:
    type: AzureOpenAIModelConfiguration
  flow_config:
    type: object
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
    assert metrics == {"expected_key": "expected_value"}
```

## Chat with a flow

Chat with flex flow in CLI is supported:

```bash
pf flow test --flow path/to/flow --inputs path/to/inputs --init path/to/init --ui
```

Check [here](../chat-with-a-flow) for more information.

## Batch run

User can batch run a flex flow with YAML like DAG flow. Flow init function's param is supported by `init` parameter.

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

User can serve a flex flow like DAG flow. Flow init function's param is supported by `init` parameter.
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



### Connection in `__init__`

### Environment variable connections(EVC)


## Aggregation support (metrics)


**Note**: 

1. The actual `line_results` passed inside `__aggregate__` function is not same object with each line's `__call__` returns.
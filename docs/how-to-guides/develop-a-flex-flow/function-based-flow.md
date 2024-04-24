# Function based flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

User can directly use a function(see [supported types](./supported-types.md) for typing support) as flex flow's entry.

## Authoring


```python
from promptflow.tracing import trace

class Reply(TypedDict):
    output: str

@trace
def my_flow(text: str) -> Reply:
    # flow logic goes here
    pass
```

**Note** tracing is supported for flex flow. Check [here](../tracing/index.md) for more information.

## YAML support

Similar as [DAG flow](../deploy-a-flow/index.md). YAML file is identifier for flex flow.
Flex flow will use `flow.flex.yaml` as it's identifier.
User can write the YAML file manually or save a function/callable entry to YAML file.
A flex flow YAML may look like this:

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json
entry: path.to.module:function_name
```

## Flow test

Since flex flow's definition is function/callable class. We recommend user directly run it like running other scripts:

```python
from flow_entry import my_flow
if __name__ == "__main__":
    output = my_flow(**call_args)
    print(output)
```

## Chat with a flow

Chat with flex flow in CLI is supported:

```bash
pf flow test --flow path/to/flow --inputs path/to/inputs --ui
```

Check [here](../chat-with-a-flow/index.md) for more information.

## Batch run without YAML

User can also batch run a flex flow without YAML.
Instead of calling `pf.save` to create flow YAML first.

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
pf run create --flow "path.to.module:function_name" --data "./data.jsonl"
```

:::

:::{tab-item} SDK
:sync: SDK
```python
# user can also directly use entry in `flow` param for batch run
pf.run(flow="path.to.module:function_name", data="./data.jsonl")
```

:::

## Batch run with YAML

User can batch run a flex flow with YAML.

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
pf run create --flow "./flow.flex.yaml" --data "./data.jsonl"
```

:::

:::{tab-item} SDK
:sync: SDK

```python
pf = PFClient()
pf.run(flow="./flow.flex.yaml", data="./data.jsonl")
```

:::

Or directly run the imported function.
**Note**: this only works in local.

```python
from path.to.module import my_flow
pf.run(flow=my_flow, data="./data.json;")
```

## Serve

User can serve a flex flow.

```bash
pf flow serve --source "./flow.flex.yaml"  --port 8088 --host localhost
```

## Build & deploy

Build & deploy a flex flow is supported like [DAG flow](../deploy-a-flow/index.md).

## Next steps

- [Class based flex flow](./class-based-flow.md)
- [Supported types](./supported-types.md)
- [Function based flex flow sample](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/basic/README.md)

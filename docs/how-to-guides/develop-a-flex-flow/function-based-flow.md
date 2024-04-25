# Function based flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

User can directly use a function as flow entry.

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

**Note** tracing is supported for flow. Check [here](../tracing/index.md) for more information.

## YAML support


User can write a YAML file with name `flow.flex.yaml` manually or save a function/callable entry to YAML file.
A flow YAML may look like this:

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json
entry: path.to.module:function_name
```

## Flow test

Since flow's definition is normal python function/callable class. We recommend user directly run it like running other scripts:

```python
from flow_entry import my_flow
if __name__ == "__main__":
    output = my_flow(**call_args)
    print(output)
```

## Chat with a flow

Chat with flow in CLI:

```bash
pf flow test --flow path/to/flow --inputs path/to/inputs --ui
```

Check [here](../chat-with-a-flow/index.md) for more information.

## Batch run without YAML

User can also batch run a flow without YAML.
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
::::

## Batch run with YAML

User can batch run a flow with YAML.

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
::::

Or directly run the imported function.
**Note**: this only works in local.

```python
from path.to.module import my_flow
pf.run(flow=my_flow, data="./data.json;")
```

## Serve

User can serve a flow.

```bash
pf flow serve --source "./flow.flex.yaml"  --port 8088 --host localhost
```

## Build & deploy

Build & deploy a flow is supported, see [Deploy a flow](../deploy-a-flow/index.md).

## Next steps

- [Class based flow](./class-based-flow.md)
- [Input output format](./input-output-format.md)
- [Function based flow sample](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/basic/README.md)

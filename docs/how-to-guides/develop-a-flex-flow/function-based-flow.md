# Function based flow

User can directly use a function(see [supported types](./index.md#supported-types) for typing support) as flex flow's entry.
**Note**: the annotation is not required, user can use `flow save` to provide signatures or write `flow.flex.yaml`.

## Authoring

```python
class Reply(TypedDict):
    output: str

@trace
def my_flow(text: str) -> Reply: 
    pass
```

## YAML support

Similar as DAG flow. YAML file is identifier for flex flow.
Flex flow will use `flow.flex.yaml` as it's identifier.
User can write the YAML file manually or save a function/callable entry to YAML file.
A complete flex flow YAML may look like this:

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json
entry: path.to.module:function_name
inputs:
    text:
        type: string
outputs:
    output:
        type: string
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

Check [here](../chat-with-a-flow) for more information.

## Batch run

User can batch run a flex flow with YAML like DAG flow.

```python
pf = PFClient()
pf.run(flow="./flow.flex.yaml", data="./data.jsonl")
```

## Batch run without YAML

User can also batch run a flex flow without YAML.
Instead of calling `pf.save` to create flow YAML first.

```python
# user can also directly use entry in `flow` param for batch run
pf.run(flow="path.to.module:function_name", data="./data.jsonl")
```

Or directly run the imported function.
**Note**: this only works in local.

```python
from path.to.module import my_flow
pf.run(flow=my_flow, data="./data.json;")
```

## Serve

User can serve a flex flow like DAG flow.

```bash
pf flow serve --source "./flow.flex.yaml"  --port 8088 --host localhost
```

## Build & deploy

Build & deploy a flex flow is supported like [DAG flow](../deploy-a-flow/).

## Tracing support

Tracing is supported for flex flow.
Check [here](../tracing/) for more information.

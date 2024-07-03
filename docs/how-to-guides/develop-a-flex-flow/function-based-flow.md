# Function based flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

User can directly use a function as flow entry.

## Function as a flow

Assume we have a file `flow_entry.py`:

```python
from promptflow.tracing import trace

class Reply(TypedDict):
    output: str

@trace
def my_flow(question: str) -> Reply:
    # flow logic goes here
    pass
```

**Note** function decorated with `@trace` will emit trace can be viewed in UI provided by PromptFlow. Check [here](../tracing/index.md) for more information.

## Flow test

### Test via function call

Since flow's definition is normal python function/callable class. We recommend user directly run it like running other scripts:

```python
from flow_entry import my_flow

if __name__ == "__main__":
    output = my_flow(question="What's the capital of France?")
    print(output)
```

### Convert to a flow and test

It's also supported to convert your function entry to a flow and test with prompt flow's ability.

You can test with the following CLI:

```bash
# flow entry syntax: path.to.module:function_name
pf flow test --flow flow_entry:my_flow --inputs question="What's the capital of France?"
```

**Note**: currently this command will generate a flow.flex.yaml in your working directory. Which will become the flow's entry.

Check out a full example here: [basic](https://github.com/microsoft/promptflow/tree/main/examples/flex-flows/basic)

### Chat with a flow

Start a UI to chat with a flow:

```bash
pf flow test --flow flow_entry:my_flow --inputs question="What's the capital of France?" --ui
```

Check [here](../chat-with-a-flow/index.md) for more information.

## Batch run

User can also batch run a flow.

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

from path.to.module import my_flow
# Note directly run function in `pf.run` is only supported in local PFClient for now 
pf.run(flow=my_flow, data="./data.jsonl")

# user can also directly use entry in `flow` param for batch run
pf.run(flow="path.to.module:function_name", data="./data.jsonl")
```
:::
::::

Learn more on this topic on [Run and evaluate a flow](../run-and-evaluate-a-flow/index.md)

## Define a flow yaml

User can write a YAML file with name `flow.flex.yaml` manually or save a function/callable entry to YAML file.
This is required for advanced scenario like deployment or run in cloud.
A flow YAML may look like this:

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/Flow.schema.json
entry: path.to.module:function_name
sample:
    inputs:
        question: "what's the capital of France?"
```

## Batch run with YAML

User can batch run a flow with YAML.

::::{tab-set}
:::{tab-item} CLI
:sync: CLI

```bash
# against flow file
pf run create --flow "path/to/flow/flow.flex.yaml" --data "./data.jsonl"
# against a folder if it has a flow.flex.yaml file
pf run create --flow "path/to/flow" --data "./data.jsonl"
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

## Deploy a flow

User can serve a flow as a http endpoint locally or deploy it to multiple platforms.

```bash
# serve locally from a folder if it has a flow.flex.yaml file
pf flow serve --source "path/to/flow/dir"  --port 8088 --host localhost

# serve locally from certain file
pf flow serve --source "./flow.flex.yaml"  --port 8088 --host localhost
```
Learn more: [Deploy a flow](../deploy-a-flow/index.md).

## Next steps

- [Class based flow](./class-based-flow.md)
- [Input output format](./input-output-format.md)
- [Function based flow sample](https://github.com/microsoft/promptflow/blob/main/examples/flex-flows/basic/README.md)

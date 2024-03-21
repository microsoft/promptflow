# Execute flow as a function

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](faq.md#stable-vs-experimental).
:::

## Overview

Promptflow allows you to load a flow and use it as a function in your code.
This feature is useful when building a service on top of a flow, reference [here](https://github.com/microsoft/promptflow/tree/main/examples/tutorials/flow-deploy/create-service-with-flow) for a simple example service with flow function consumption.

## Load and invoke the flow function

To use the flow-as-function feature, you first need to load a flow using the `load_flow` function.
Then you can consume the flow object like a function by providing key-value arguments for it.

```python
f = load_flow("../../examples/flows/standard/web-classification/")
f(url="sample_url")
```

## Config the flow with context

You can overwrite some flow configs before flow function execution by setting `flow.context`.

### Load flow as a function with in-memory connection override

By providing a connection object to flow context, flow won't need to get connection in execution time, which can save time when for cases where flow function need to be called multiple times.

```python
from promptflow.entities import AzureOpenAIConnection

connection_obj = AzureOpenAIConnection(
    name=conn_name,
    api_key=api_key,
    api_base=api_base,
    api_type="azure",
    api_version=api_version,
)
# no need to create the connection object.  
f.context = FlowContext(
    connections={"classify_with_llm": {"connection": connection_obj}}
)
```

### Local flow as a function with flow inputs override

By providing overrides, the original flow dag will be updated in execution time.

```python
f.context = FlowContext(
    # node "fetch_text_content_from_url" will take inputs from the following command instead of from flow input
    overrides={"nodes.fetch_text_content_from_url.inputs.url": sample_url},
)
```

**Note**, the `overrides` are only doing YAML content replacement on original `flow.dag.yaml`.
If the `flow.dag.yaml` become invalid after `overrides`, validation error will be raised when executing.

### Load flow as a function with streaming output

After set `streaming` in flow context, the flow function will return an iterator to stream the output.

```python
f = load_flow(source="../../examples/flows/chat/chat-basic/")
f.context.streaming = True
result = f(
    chat_history=[
        {
            "inputs": {"chat_input": "Hi"},
            "outputs": {"chat_output": "Hello! How can I assist you today?"},
        }
    ],
    question="How are you?",
)


answer = ""
# the result will be a generator, iterate it to get the result
for r in result["answer"]:
    answer += r

```

Reference our [sample](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/get-started/flow-as-function.ipynb) for usage.

## Flow with multiple overrides

**Note**: the flow context configs may affect each other in some cases. For example, using `connection` & `overrides` to override same node.
The behavior is undefined for those scenarios. Pleas avoid such usage.

```python
# overriding `classify_with_llm`'s connection and inputs in the same time will lead to undefined behavior.
f.context = FlowContext(
    connections={"classify_with_llm": {"connection": connection_obj}},
    overrides={"nodes.classify_with_llm.inputs.url": sample_url}
)
```

## Next steps

Learn more about:

- [Flow as a function sample](https://github.com/microsoft/promptflow/blob/main/examples/tutorials/get-started/flow-as-function.ipynb)
- [Deploy a flow](./deploy-a-flow/index.md)

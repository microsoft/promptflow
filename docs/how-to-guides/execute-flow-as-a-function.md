# Set global configs
:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](faq.md#stable-vs-experimental).
:::

## Overview

Promptflow allows you to load a flow and use it as a function in your code.
This feature is useful when building a service on top of a flow, reference [here](../../examples/tutorials/flow-deploy/create-service-with-flow/) for a simple example service with flow function consumption.

## Load an invoke the flow function

To use the Flow-as-Function feature, you first need to load a flow using the `load_flow` function.
Then you can consume the flow object like a function by providing key-value arguments for it.

```python
f = load_flow("../../flows/standard/web-classification")
f(url="sample_url")
```

## Config the flow with context

You can overwrite some flow configs before flow function execution by setting `flow.context`.

### Load flow as a function with in-memory connection override

By providing a connection object to flow context, flow won't need to get connection in execution time, which can save time when for cases where flow function need to be called multiple times.

```python
f.context = FlowContext(
    connections={"classify_with_llm": {"connection": connection_object}}
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

### Load flow as a function with streaming output

After set `streaming` in flow context, the flow function will return an iterator to stream the output.

```python
f.context.streaming = True
```

Reference our [sample](../../examples/tutorials/get-started/flow-as-function.ipynb) for usage.

## Next steps

Learn more about:

- [Flow as a function sample](../../examples/tutorials/get-started/flow-as-function.ipynb)
- [Deploy a flow](../deploy-a-flow/index.md)

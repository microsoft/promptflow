# Develop a flex flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

Flex flow is short cut for flexible flow, which means it works for most scenarios with little adjustment.

We provide guides on how to develop a flow by writing a flow yaml from scratch in this section.

Flex flow provides a new way to deploy your LLM app in prompt flow.
Which has the following benifits:

- Quick start (playground experience). Users can quickly test with prompt + python code with UI visualize experience. For example, user don't necessarily have to create YAML to run flex flow. See [batch run without YAML](./function-based-flow.md#batch-run-without-yaml) for more information.
- More advanced orchestration. Users can write complex flow with Python built-in control operators (if-else, foreach) or other 3rd party / open-source library. 
- Easy onboard from other platforms: other platforms like langchain and sematic kernel already have code first flow authoring experience. We can onboard those customers with a few code changes.

## Stream

Stream is supported in flex flow.
Reference this [sample](https://microsoft.github.io/promptflow/tutorials/stream-flex-flow.html) for details.

```{toctree}
:maxdepth: 1

function-based-flow
class-based-flow
supported-types
```

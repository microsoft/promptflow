# Develop a flow

:::{admonition} Experimental feature
This is an experimental feature, and may change at any time. Learn [more](../faq.md#stable-vs-experimental).
:::

You can create LLM apps using a Python function or class as the entry point, which encapsulating your app logic. You can directly test or run these entries with pure code experience. 

In PromptFlow, these functions or classes are referred to as `flow` or `flex flow`. 

Alternatively, you can define a `flow.flex.yaml` that points to these entries (`entry:function_name` or `entry:ClassName`). This enables testing, running, or viewing traces via the [Promptflow VS Code Extension](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow).

Our [examples](https://github.com/microsoft/promptflow/tree/main/examples/flex-flows) should give you a good idea on how to write flows.

Note: 
- The term *Flex* is a shorthand for *flexible*, indicating its adaptability to most scenarios with minimal adjustments.
- PromptFlow also supports the development of a `dag flow`. learn more on comparasion of these two [flow concepts](../../concepts/concept-flows.md).


```{toctree}
:maxdepth: 1

function-based-flow
class-based-flow
input-output-format
model-config
connection-support
```

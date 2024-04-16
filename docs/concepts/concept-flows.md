While how LLMs work may be elusive to many developers, how LLM apps work is not - they essentially involve a series of calls to external services such as LLMs/databases/search engines, or intermediate data processing, all glued together.

# Flows

## Flex flows

{bdg-success-line}`New in version 1.9.0`

You can create LLM apps using a Python function or class as the entry point, which encapsulating your app logic. You can directly test or run these with pure code experience. Or you can define a `flow.flex.yaml` that points to these entries, which enables testing, running, or viewing traces via the [Promptflow VS Code Extension](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow).

Our [examples](https://github.com/microsoft/promptflow/tree/main/examples/flex-flows) should also give you an idea how to write `flex flows`.

## DAG flow

Thus LLM apps can be defined as Directed Acyclic Graphs (DAGs) of function calls. These DAGs are flows in prompt flow.

A flow in prompt flow is a DAG of functions (we call them [tools](./concept-tools.md)). These functions/tools connected via input/output dependencies and executed based on the topology by prompt flow executor.

A flow is represented as a YAML file and can be visualized with our [Prompt flow for VS Code extension](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow). Here is an example `flow.dag.yaml`:

![flow_dag](../media/how-to-guides/quick-start/flow_dag.png)

Please refer to our [examples](https://github.com/microsoft/promptflow/tree/main/examples/flows) to learn how to write a `DAG flow`. 

## Flow types

Prompt flow examples organize flows by three categories:

- **Standard flow** or **Chat flow**: these two are for you to develop your LLM application. The primary difference between the two lies in the additional support provided by the "Chat Flow" for chat applications. For instance, you can define `chat_history`, `chat_input`, and `chat_output` for your flow. The prompt flow, in turn, will offer a chat-like experience (including conversation history) during the development of the flow. Moreover, it also provides a sample chat application for deployment purposes.
- **Evaluation flow** is for you to test/evaluate the quality of your LLM application (standard/chat flow). It usually run on the outputs of standard/chat flow, and compute some metrics that can be used to determine whether the standard/chat flow performs well. E.g. is the answer accurate? is the answer fact-based?


Flex flow [examples](https://github.com/microsoft/promptflow/tree/main/examples/flex-flows):
- [basic](https://github.com/microsoft/promptflow/tree/main/examples/flex-flows/basic)
- [chat-basic](https://github.com/microsoft/promptflow/tree/main/examples/flex-flows/chat-basic)
- [eval-basic](https://github.com/microsoft/promptflow/tree/main/examples/flex-flows/eval-basic)

DAG flow [examples](https://github.com/microsoft/promptflow/tree/main/examples/flows):
- [basic](https://github.com/microsoft/promptflow/tree/main/examples/flows/standard/basic)
- [chat-basic](https://github.com/microsoft/promptflow/tree/main/examples/flows/chat/chat-basic)
- [eval-basic](https://github.com/microsoft/promptflow/tree/main/examples/flows/evaluation/eval-basic)


## Next steps

- [Quick start](../how-to-guides/quick-start.md)
- [Initialize and test a flow](../how-to-guides/init-and-test-a-flow.md)
- [Run and evaluate a flow](../how-to-guides/run-and-evaluate-a-flow/index.md)
- [Tune prompts using variants](../how-to-guides/tune-prompts-with-variants.md)
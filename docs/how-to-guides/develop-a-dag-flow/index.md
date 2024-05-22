# Develop a dag flow

LLM apps can be defined as Directed Acyclic Graphs (DAGs) of function calls. These DAGs are flows in prompt flow.

A `DAG flow` in prompt flow is a DAG of functions (we call them [tools](../../concepts//concept-tools.md)). These functions/tools connected via input/output dependencies and executed based on the topology by prompt flow executor.

A flow is represented as a YAML file and can be visualized with our [Prompt flow for VS Code extension](https://marketplace.visualstudio.com/items?itemName=prompt-flow.prompt-flow). Here is an example `flow.dag.yaml`:

![flow_dag](../../media/how-to-guides/quick-start/flow_dag.png)

Please refer to our [examples](https://github.com/microsoft/promptflow/tree/main/examples/flows) and guides in this section to learn how to write a `DAG flow`. 

Note: 
- promptflow also support user develop a a flow using code. learn more on comparasion of these two [flow concepts](../../concepts/concept-flows.md).

```{toctree}
:maxdepth: 1

quick-start
init-and-test-a-flow
develop-standard-flow
develop-chat-flow
develop-evaluation-flow
add-conditional-control-to-a-flow
process-image-in-flow
referencing-external-files-or-folders-in-a-flow
```
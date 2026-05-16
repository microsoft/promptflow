# Phase 2 — Rebuild in MAF

Re-implement your Prompt Flow application using MAF's `WorkflowBuilder`
and `Executor` pattern. Work through the samples in numbered order.

## Samples

| File | Prompt Flow pattern it replaces |
|---|---|
| [01_linear_flow.py](01_linear_flow.py) | Input node → LLM node |
| [02_python_node.py](02_python_node.py) | Python code node with custom logic |
| [03_conditional_flow.py](03_conditional_flow.py) | If / conditional node |
| [04_parallel_flow.py](04_parallel_flow.py)| Parallel nodes with no shared dependencies |
| [05_rag_flow.py](05_rag_flow.py) | Embed Text + Vector Lookup + LLM nodes (full RAG pipeline) |
| [06_function_tools.py](06_function_tools.py) | Python tool node → function tools |
| [07_multi_agent.py](07_multi_agent.py) | Multi-step specialist routing → `HandoffBuilder` multi-agent handoff |

## Run any sample

```bash
cd phase-2-rebuild
python 01_linear_flow.py
```

## Visualize a workflow in DevUI

[`agent-framework-devui`](https://github.com/microsoft/agent-framework/tree/main/python/packages/devui)
is a lightweight web app for inspecting the executor graph of a MAF workflow
and running it interactively. [visualize_workflow.py](visualize_workflow.py)
loads the module-level `workflow` object from one or more samples in this
folder and hands them to DevUI's `serve()`.

```bash
# One-time install (preview package)
pip install agent-framework-devui --pre

cd phase-2-rebuild

# Visualize all 7 samples — pick one from the entity dropdown in the UI
python visualize_workflow.py

# Or visualize a single sample
python visualize_workflow.py --file 03_conditional_flow.py

```

By default the UI opens at <http://127.0.0.1:8080>. Pass `--port`, `--host`,
or `--no-open` to override. Make sure your `.env` is filled in (see
[.env.example](../.env.example)) — the samples that use `FoundryChatClient`
or Azure AI Search will fail to load otherwise.

## The pattern every sample follows

- Define Executors — one class per logical step, each with a @handler method
- Build the Workflow — connect executors with WorkflowBuilder and .add_edge()
- Run — await workflow.run(input), read output from result.get_outputs()

See [node-mapping](../phase-1-audit/node-mapping.md) for the full PF → MAF concept mapping.

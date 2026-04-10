# Prompt Flow → MAF Node Mapping

| Prompt Flow Concept | MAF Equivalent | Sample |
|---|---|---|
| Flow (YAML / visual graph) | `Workflow` built with `WorkflowBuilder` | All samples |
| Node (any step) | `Executor` class with a `@handler` method | All samples |
| LLM node | `AzureOpenAIChatClient().as_agent(instructions=...)` inside an `Executor` | `01_linear_flow.py` |
| Python node | Plain Python logic inside an `Executor @handler` | `02_python_node.py` |
| Prompt node | String formatting inside an `Executor @handler` | `02_python_node.py` |
| Embed Text + Vector Lookup nodes | `AzureAISearchContextProvider` via `context_providers=[...]` | `05_rag_flow.py` |
| If / conditional node | `.add_edge(source, target, condition=fn)` | `03_conditional_flow.py` |
| Parallel nodes (no dependencies) | `.add_fan_out_edges(source, [targetA, targetB])` | `04_parallel_flow.py` |
| Merge / aggregate node | `.add_fan_in_edges([sourceA, sourceB], target)` | `04_parallel_flow.py` |
| Flow Inputs | Type annotation on the start `Executor`'s `@handler` parameter | All samples |
| Flow Outputs | `await ctx.yield_output(value)` in the terminal `Executor` | All samples |
| Connections (credentials) | Environment variables read automatically by MAF clients | `.env.example` |
| Evaluation flow | `SimilarityEvaluator` from Azure AI Evaluation SDK | `phase-3-validate/` |
| Managed Online Endpoint | FastAPI wrapper + Azure Container Apps, or Foundry Agent Service | `phase-4-migrate-ops/4b-deployment/` |

---

## WorkflowContext type parameters

| Annotation | Behaviour |
|---|---|
| `WorkflowContext` | Side effects only — no output sent |
| `WorkflowContext[str]` | Sends a `str` downstream via `ctx.send_message()` |
| `WorkflowContext[Never, str]` | Yields a `str` as the final workflow output via `ctx.yield_output()` |
| `WorkflowContext[str, str]` | Both sends a message downstream AND yields a workflow output |

`Never` is imported from `typing_extensions`.

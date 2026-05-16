# Evaluation Flows (`aggregation: true`)

> **Read this when** any node in `flow.dag.yaml` has `aggregation: true`.

An evaluation flow has two phases:
- **Per-row phase** — runs the non-aggregation nodes once per dataset row (concurrently)
- **Aggregation phase** — collects all per-row outputs and computes batch metrics

In MAF, this maps to:
- A per-row `WorkflowBuilder` workflow (no aggregation node)
- A standalone Python aggregation function
- An `EvalRunner` orchestrator that runs the workflow per row and feeds outputs to the aggregator

## File layout

The generated `<original>-maf/` folder for an evaluation flow must contain:

| File | Purpose |
|------|---------|
| `workflow.py` | Per-row MAF workflow + `create_workflow()` factory |
| `aggregation.py` | Standalone aggregation function(s) extracted from the original `aggregation: true` node(s) |
| `eval_runner.py` | Reusable `EvalRunner` class — copy [templates/eval_runner.py](../templates/eval_runner.py) verbatim |
| `run_eval.py` | Entry point: load dataset, instantiate `EvalRunner`, print metrics |
| `requirements.txt`, `.env.example` | As usual |

## Phase 1 — Audit additions

When auditing the source flow, also identify:

- **Per-row nodes** — all nodes WITHOUT `aggregation: true`
- **Aggregation nodes** — all nodes WITH `aggregation: true`
- **Aggregation inputs** — which per-row node outputs feed into the aggregation node (e.g., `${grade.output}` → `grades: List[str]`)

## Generating the per-row `workflow.py`

Build a `WorkflowBuilder` containing **only** the non-aggregation nodes. Export a `create_workflow()` factory function (not a module-level singleton) so `EvalRunner` can create a fresh instance per concurrent row.

## Generating `aggregation.py`

Extract each aggregation node's Python function as a standalone function:

- Remove the `@tool` decorator
- Remove `from promptflow.core import log_metric` and all `log_metric()` calls
- Instead of calling `log_metric(key, value)`, include the metric in the returned `dict`
- Keep the function signature (parameter names and types) identical to the original
- The function must return a `dict` mapping metric names to values

## Generating `run_eval.py`

Configure the `EvalRunner`:

- `workflow_factory` → the `create_workflow` function from `workflow.py`
- `aggregate_fn` → the aggregation function from `aggregation.py`
- `input_mapping` → maps transposed key names to aggregation function parameter names

### Input mapping rules

`EvalRunner._transpose()` converts per-row outputs into keyword args for the aggregation function:

| Per-row output type | `_transpose()` produces | `input_mapping` needed? |
|---|---|---|
| Plain value (`str`, `int`, `float`) | `{"values": [v1, v2, ...]}` | Yes — map `"values"` → aggregation param name (e.g., `{"values": "processed_results"}`) |
| Dict (e.g., `{"coherence": 4.2, "fluency": 2.5}`) | `{"coherence": [4.2, ...], "fluency": [2.5, ...]}` | Only if dict keys differ from aggregation param names |

For multi-output flows (e.g., `eval-summarization` with 4 scores per row), the per-row workflow should yield a dict whose keys match the aggregation function's parameter names. Then no `input_mapping` is needed.

## EvalRunner template

Copy [templates/eval_runner.py](../templates/eval_runner.py) verbatim into the output folder. It is identical across all evaluation flows.

## Complete example

See [examples/evaluation.md](../examples/evaluation.md) for a full converted evaluation flow.

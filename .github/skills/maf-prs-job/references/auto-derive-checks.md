# Phase 1.5 — Auto-derive Verdict Checks

Run these checks **before** generating files to decide which fields the
agent can fill automatically vs. which must be left as `# TODO` stubs for
the user. Print the resulting verdict table to the user before writing
any code.

> Rule of thumb: **never invent values.** When in doubt, emit a TODO with
> a comment quoting the original PF source and the reason auto-derivation
> stopped.

---

## Input side — `hooks.build_workflow_input(row)`

The first failure stops auto-derivation; the function becomes a TODO stub.

| # | Check | What "enough info" looks like | If missing |
|---|---|---|---|
| **A** | Mapping is parseable | Every kwarg in `flow_node(...)` that is **not** a known PRS setting (`compute`, `mini_batch_size`, `connections`, etc.) has a value that fully matches `r"\$\{data\.([\w\.]+)\}"`. | TODO: "PF mapping uses non-trivial expression `<value>` — fill manually." |
| **B** | Mapping is non-empty | At least one `${data.col}` was found. | Default to `return row` (pass-through). No TODO needed if the workflow's first executor accepts a free-form `dict`. |
| **C** | Start handler is typed | `inspect.signature(start_executor.handler)` shows a typed first non-`self`, non-`ctx` parameter. Accepted: `str`, `int`, `float`, `bool`, `dict`, `dict[str, Any]`, a `@dataclass`, a `pydantic.BaseModel` subclass, or `agent_framework.ChatMessage`. | TODO: "Workflow start handler input is `Any` / untyped — cannot infer shape; map row to handler input manually." |
| **D** | Mapping fields fit handler | The PF target field names match the handler input's fields (for `dict` / dataclass / Pydantic), or there is exactly one PF mapping (for scalar handler input). | TODO: "PF mapping fields `<a, b>` do not match handler `<C>` fields `<x, y>` — fill manually." |

When A–D **all** pass, emit one of these bodies:

| Handler input type | Mapping shape | Generated body |
|---|---|---|
| `str` / `int` / `float` / `bool` | exactly one `${data.col}` | `return row["col"]` |
| `dict` / `dict[str, Any]` | N `${data.col_i}` → N target fields | `return {"f1": row["c1"], ...}` |
| `@dataclass` / `BaseModel` / `ChatMessage` | N `${data.col_i}` → N target fields matching the model | `return MyInput(f1=row["c1"], ...)` (plus an `import` line at the top of `hooks.py`) |

### TODO stub template

```python
def build_workflow_input(row: dict):
    # TODO: PF mapping was flow_node(input="${data.url}")
    # but the workflow's start executor handler is untyped (Any),
    # so the input shape cannot be inferred. Replace this with a
    # call that returns the object your start executor expects.
    raise NotImplementedError("Fill build_workflow_input for your workflow.")
```

---

## Output side — `hooks.serialize_output(output)`

| # | Check | What "enough info" looks like | If missing |
|---|---|---|---|
| **E** | Terminal output type is inspectable | The workflow's terminal executor calls `ctx.set_output(<typed value>)` or yields `WorkflowOutputEvent(payload=<typed value>)` where the payload type is a class the agent can resolve via AST. | Keep the **default** `serialize_output` from the template (the duck-typed fallback works for most cases). Add a comment: `# auto: kept default — verify against your workflow output shape.` Do **not** leave a hard TODO. |

---

## Connection inputs — `component.yaml` + `submit_pipeline.py`

| # | Check | What "enough info" looks like | If missing |
|---|---|---|---|
| **F** | Connection kwargs identifiable | `flow_node(connections={...})` (or per-node kwargs like `connection=`, `deployment_name=`, `model=`, `api_version=`) are present in the source script. | `# TODO` in `component.yaml::inputs` and a `# TODO` for `MODEL_ENDPOINT` / `MODEL_DEPLOYMENT` constants in `submit_pipeline.py`. |
| **G** | Endpoint URL resolvable | The PF connection name maps to a known Azure resource the user has already deployed (or is provided in the audit). | Leave the `MODEL_ENDPOINT = "https://<your-foundry-resource>..."` placeholder and tell the user what to fill. **Never** invent an endpoint URL. |

---

## Data input/output ports

| # | Check | What "enough info" looks like | If missing |
|---|---|---|---|
| **H** | Input data path/type/mode | `Input(path=..., type=..., mode=...)` literally appears in the source script (or a notebook cell). | Leave the `data_input = Input(...)` block in `submit_pipeline.py` with a `# TODO` placeholder. |
| **I** | Local sample copy needed? | The user wants the generated project to be self-contained for local dry-run **and** the source `Input(path=...)` resolves to a local file the agent can read. | **Default: do nothing.** Reuse the source `Input(...)` verbatim in `submit_pipeline.py` and **do not** create `data/sample.jsonl`. Add a note in the verdict table: "reused source data input; local dry-run requires you to point `data/` at a small local file." Only copy when both conditions hold; never invent a sample. |
| **J** | Pipeline output path | `pipeline_output = Output(path=..., ...)` is set with a literal datastore URI. | Keep the template's commented-out `path=` line and tell the user it will land in the default workspace blobstore. |

---

## Verdict table (show to the user)

After running checks A–J, print a table like this **before** writing any
files. The same table doubles as the change log handed to the user at
the end.

| Method / file | Status | Notes |
|---|---|---|
| `hooks.build_workflow_input` | ✅ auto-filled | maps `${data.url}` → `row["url"]` |
| `hooks.serialize_output` | ✅ default kept | output type `str` matches duck-typed fallback |
| `hooks.setup` | ✅ auto-filled | translates `model_endpoint` / `model_deployment` to env vars |
| `component.yaml::inputs` | ✅ auto-filled | from `connection="aoai_conn", deployment_name="gpt-4o"` |
| `submit_pipeline.py::MODEL_ENDPOINT` | ⚠️ TODO | PF connection name `aoai_conn` not resolvable to a deployed resource |
| `submit_pipeline.py::data_input` | ✅ auto-filled | preserved source `Input(path="azureml://...", type=URI_FILE, mode="ro_mount")` verbatim |
| `data/sample.jsonl` | ➖ not created | reused source data input; provide a local file path here only if you want a self-contained dry-run |

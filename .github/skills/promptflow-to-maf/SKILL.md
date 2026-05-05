---
name: promptflow-to-maf
description: "Convert Prompt Flow flow definitions to Microsoft Agent Framework (MAF) workflows. Parses flow.dag.yaml, maps nodes to Executors, and generates runnable Python code using agent-framework 1.0.x. WHEN: convert promptflow, migrate promptflow, promptflow to MAF, promptflow to agent framework, convert flow.dag.yaml, migrate flow to MAF, convert PF flow, PF to agent-framework, convert DAG flow to workflow, migrate LLM flow. DO NOT USE FOR: writing new MAF workflows from scratch (no source flow), deploying MAF workflows (use maf-online-endpoint), enabling tracing (use maf-tracing), or general agent-framework Q&A."
license: MIT
metadata:
  author: Team
  version: "2.0.0"
---

# Prompt Flow → Microsoft Agent Framework Conversion

> Convert Prompt Flow `flow.dag.yaml` definitions into runnable MAF `WorkflowBuilder` Python code.

## Triggers

Activate this skill when the user wants to:
- Convert a Prompt Flow flow to Microsoft Agent Framework
- Migrate a `flow.dag.yaml` to MAF workflow code
- Rebuild a Prompt Flow application using `agent-framework`

---

## What to Read When (Progressive Disclosure)

This skill is split across multiple files. **Always read this file first.** Then read additional files based on what the source flow contains:

| Situation | Required Reading |
|---|---|
| **Every conversion task** | This file + [references/gotchas.md](references/gotchas.md) |
| Need to map a specific node type | [references/node-mapping.md](references/node-mapping.md) |
| Writing Executor handlers / picking LLM client / setting `temperature`/`max_tokens` | [references/workflow-context.md](references/workflow-context.md) |
| Source flow has a node with `source.type: package` | [topics/custom-tool-nodes.md](topics/custom-tool-nodes.md) |
| Source flow has image / multimodal inputs | [topics/multimodal.md](topics/multimodal.md) + [examples/multimodal-chat.md](examples/multimodal-chat.md) |
| Source flow has any node with `aggregation: true` | [topics/evaluation-flows.md](topics/evaluation-flows.md) + [templates/eval_runner.py](templates/eval_runner.py) + [examples/evaluation.md](examples/evaluation.md) |
| Source flow references PF connections (LLM node `connection:` field, or custom-tool input `connection: ...`) | [topics/connections.md](topics/connections.md) |
| Want a complete reference example | [examples/linear-chat.md](examples/linear-chat.md) (basic), [examples/multimodal-chat.md](examples/multimodal-chat.md), [examples/evaluation.md](examples/evaluation.md) |

> **Don't pre-load everything.** Read each file lazily when its situation is detected during Phase 1 audit.

---

## Core Rules (apply to every conversion)

1. **Read the source flow first** — Always parse `flow.dag.yaml`, all referenced source files (`.jinja2`, `.py`), and `requirements.txt` before generating anything.
2. **Preserve prompts verbatim** — System prompts, user prompt templates, and any text from `.jinja2` or inline prompt nodes must be copied exactly as they appear in the original Prompt Flow. Do not rephrase, summarize, add, or remove any content — including examples, instructions, formatting, and preambles (e.g., "Read the following conversation and respond:"). The MAF workflow must send the identical prompt text to the LLM.
3. **One Executor per node** — Each Prompt Flow node becomes one `Executor` subclass with a `@handler` method. (Some node combinations may be safely merged — see [references/node-mapping.md](references/node-mapping.md) for "Node Collapsing Patterns".)
4. **Preserve behaviour** — The MAF workflow must produce the same outputs for the same inputs as the original flow.
5. **Use GA packages** — `agent-framework>=1.0.1`, `agent-framework-openai>=1.0.1`. Use preview packages (`--pre`) only for orchestrations, Azure AI Search, or multi-agent features. (Full table in [references/workflow-context.md](references/workflow-context.md).)
6. **Create output folder** — Place generated files in a sibling folder named `<original-folder>-maf/`.
7. **Copy user-defined Python packages** — If the flow imports from internal packages (e.g., `my_utils/`, helper modules), copy the entire package directory into the output folder. The MAF workflow imports directly from the local copy — no `sys.path` manipulation needed.
8. **Generate a test sample** — Always include a runnable `test_<name>.py` sample script.
9. **Never modify the original flow** — All output goes into the new folder.
10. **Evaluation flows use the EvalRunner pattern** — If any node has `aggregation: true`, the flow is an evaluation flow. See [topics/evaluation-flows.md](topics/evaluation-flows.md).
11. **Always export a `create_workflow()` factory** — MAF workflows do not support concurrent `run()` calls on a single instance (`RuntimeError: Workflow is already running`). Every generated `workflow.py` must export a `create_workflow()` factory function that creates a fresh workflow instance per call. Do NOT instantiate Executors or build the workflow at module level. This ensures callers can safely run multiple workflows concurrently (e.g., evaluation batches, parallel API requests, or test suites). For evaluation flows, `EvalRunner` relies on this factory to create one workflow per row.
12. **Copy ALL referenced resources into the output folder** — The generated `-maf/` project must be fully self-contained with zero dependencies on the original Prompt Flow folder. Copy every resource file the flow references:
    - **Data files** (`.jsonl`, `.csv`, `.json`, `.tsv`) used for testing or evaluation
    - **Prompt / template files** (`.jinja2`, `.md` used as prompts)
    - **User-defined Python modules** (`.py` files or packages imported by nodes — see rule 7)
    - **Any other non-code assets** (e.g., `samples.json`, config files, image assets)

    Update all file path references (e.g., `DEFAULT_DATA`, `_TEMPLATES_DIR`, `_PROMPT_TEMPLATE`) to point to the local copy using `Path(__file__).parent / ...`. Never use `parent.parent` or relative paths that reach back into the original flow directory.

---

## Conversion Workflow (4 Phases)

### Phase 1 — Audit the Prompt Flow

1. **Read `flow.dag.yaml`** — identify all inputs, outputs, nodes, their types, and edges (data references like `${node.output}`).
   - For every node, record `type` AND `source.type`. **A node with `source.type: package` is a custom user-defined tool — read [topics/custom-tool-nodes.md](topics/custom-tool-nodes.md) and call it directly from the Executor; do NOT remap to `OpenAIChatClient`/`Agent`.**
2. **Read source files** — open every `.jinja2` template, every `.py` file referenced by `source.type: code` nodes, and the package source for every `source.type: package` node.
3. **Read `requirements.txt`** — note any extra dependencies.
4. **Map the graph** — draw the node dependency graph from `${...}` references. Identify:
   - Linear chains (A → B → C)
   - Parallel branches (A → B, A → C)
   - Conditional branches (`activate_config`)
   - Fan-in / aggregation points
5. **Detect special cases — load the matching topic file:**
   - Any node with `aggregation: true` → evaluation flow → load [topics/evaluation-flows.md](topics/evaluation-flows.md)
   - Any node with `source.type: package` → custom tool → load [topics/custom-tool-nodes.md](topics/custom-tool-nodes.md)
   - Any image inputs (dict with `data:image/*;url` key, or string starting with `data:image/`) → multimodal → load [topics/multimodal.md](topics/multimodal.md)
   - Any LLM node has a `connection:` field, or any custom-tool node passes a `connection: ...` input → load [topics/connections.md](topics/connections.md). For each unique connection name, resolve the auth mode (key vs Microsoft Entra / managed identity vs custom) by inspecting any local connection YAML in the repo, otherwise running `pf connection show` / `az ml connection show`, otherwise inferring from `.env` / deployment files. Record the result for use in Phase 2.

### Phase 2 — Generate MAF Code

6. **Create output folder** — `<original-folder>-maf/`.
7. **Copy internal packages** — see Rule 7 above.
8. **Copy all referenced resources** — see Rule 12 above.
9. **Create one Executor per node** following [references/node-mapping.md](references/node-mapping.md).
10. **Wire the workflow inside a `create_workflow()` factory function** using `WorkflowBuilder`. Executor instantiation and `WorkflowBuilder.build()` must happen inside this function — not at module level — so each call returns a fresh, independent workflow instance:
    - `.add_edge(source, target)` for linear connections
    - `.add_edge(source, target, condition=fn)` for conditionals
    - `.add_fan_out_edges(source, [targets])` for parallel branches
    - `.add_fan_in_edges([sources], target)` for aggregation
11. **Handle LLM nodes**:
    - Extract system prompt from `.jinja2` template → `Agent(instructions="...")`
    - Pick the right client — see [references/workflow-context.md](references/workflow-context.md)
    - **Pick the right auth template** based on the connection auth mode resolved in Phase 1 step 5: emit the key template (`api_key=os.environ[...]`) or the identity template (`credential=DefaultAzureCredential()`). See [topics/connections.md](topics/connections.md) for both templates and edge cases.
    - `Agent.run()` returns an `AgentResponse` — extract text with `.text`
    - **Preserve LLM parameters** — pass `temperature`, `max_tokens`, etc. via `OpenAIChatOptions` (see [references/workflow-context.md](references/workflow-context.md))
12. **Handle chat history** — format prior turns into a prompt string in an InputExecutor, not as raw message dicts.
13. **Handle Python tool nodes** — convert to plain functions and pass to `Agent(tools=[fn])`.
14. **For evaluation flows / multimodal flows / custom-tool nodes** — follow the topic file you loaded in Phase 1 step 5.

### Phase 3 — Generate Supporting Files

15. **`requirements.txt`** — include only needed `agent-framework-*` packages. Add `azure-identity>=1.15.0` if any LLM client uses the identity template.
16. **`.env.example`** — template with required environment variables (endpoint, model, key only if the connection uses key auth). Group entries by the original PF connection name in comments. See [topics/connections.md](topics/connections.md) §3a.
17. **`test_<name>.py`** — runnable sample script exercising single-turn and multi-turn (if applicable).
18. **`README.md`** — brief setup and run instructions. Always include a **Configuration** section mapping each old PF connection to its new env vars when the flow had any connections — see [topics/connections.md](topics/connections.md) §3b. (Other documentation only if the user requests it.)

### Phase 4 — Validate

19. **Create a virtual environment** and install dependencies.
20. **Run the test sample** to verify the workflow produces output.
21. **Fix errors** — see [references/gotchas.md](references/gotchas.md).

---

## Skill File Index

```
.github/skills/promptflow-to-maf/
├── SKILL.md                       ← This file: rules + 4-phase workflow + routing
├── references/
│   ├── node-mapping.md            ← Prompt Flow node → MAF mapping table + collapse patterns
│   ├── workflow-context.md        ← WorkflowContext types, LLM clients, ChatOptions, packages
│   └── gotchas.md                 ← Common pitfalls, runtime errors, anti-patterns
├── topics/
│   ├── custom-tool-nodes.md       ← Handling source.type: package nodes
│   ├── multimodal.md              ← Image/multimodal input handling
│   ├── evaluation-flows.md        ← aggregation: true + EvalRunner pattern
│   └── connections.md             ← PF connections → env vars / DefaultAzureCredential / customer setup
├── templates/
│   └── eval_runner.py             ← Reusable runner — copy verbatim into eval flow output
└── examples/
    ├── linear-chat.md             ← Single LLM node + chat history
    ├── multimodal-chat.md         ← Image inputs (GPT-4V style)
    └── evaluation.md              ← Per-row workflow + aggregation function + run_eval.py
```

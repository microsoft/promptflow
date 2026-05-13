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
13. **Preserve graph topology and conditions exactly** — The MAF workflow's graph structure MUST be equivalent to the original `flow.dag.yaml` graph. Specifically:
    - **Node coverage** — Every Prompt Flow node must map to exactly one MAF Executor (or be merged via an explicitly allowed Collapsing Pattern; see [references/node-mapping.md](references/node-mapping.md)). No PF node may be silently dropped, and no extra Executors may be invented that don't correspond to a PF node or an allowed merge.
    - **Edge coverage** — Every data reference `${node.output}` in `flow.dag.yaml` must correspond to a MAF edge (`add_edge` / `add_fan_out_edges` / `add_fan_in_edges`) connecting the equivalent Executors. No edges may be added or removed.
    - **Parallelism preserved** — If two PF nodes run in parallel from a shared upstream node, they must remain parallel in MAF (`add_fan_out_edges`). Do NOT serialize parallel branches. If multiple PF nodes fan into one downstream node, they must use `add_fan_in_edges`.
    - **Conditions preserved** — Every `activate_config` (when/is) in PF must become an `add_edge(..., condition=fn)` with semantically identical predicate logic. The truth value of the condition for any given input must match the original.
    - **No reordering** — The execution order implied by the dependency graph must be preserved. Do not move logic from a downstream node into an upstream node (or vice versa) in a way that changes when work happens relative to other branches.
    - **Mapping table required** — In Phase 1, produce an explicit PF-node → MAF-Executor / edge mapping table (see Phase 1 step 6) and verify it in Phase 4 (see Phase 4 step 22). Any allowed merge must be annotated with the matching Collapsing Pattern from [references/node-mapping.md](references/node-mapping.md).

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
6. **Produce a node-mapping table** — Before writing any MAF code, emit (in your reasoning or as a comment block at the top of `workflow.py`) an explicit table that lists, for every PF node:
   - PF node name and `type` (+ `source.type`)
   - The MAF Executor it maps to (or the merged Executor name, with the matching Collapsing Pattern from [references/node-mapping.md](references/node-mapping.md))
   - The incoming edges (PF `${...}` references → MAF `add_edge` / `add_fan_in_edges`)
   - The outgoing edges (PF downstream consumers → MAF `add_edge` / `add_fan_out_edges`)
   - Any `activate_config` → the MAF `condition=fn` it becomes

   This table is the contract used to verify graph equivalence in Phase 4. Every PF node must appear; every `${...}` reference must appear as an edge.

### Phase 2 — Generate MAF Code

7. **Create output folder** — `<original-folder>-maf/`.
8. **Copy internal packages** — see Rule 7 above.
9. **Copy all referenced resources** — see Rule 12 above.
10. **Create one Executor per node** following the mapping table from Phase 1 step 6 and [references/node-mapping.md](references/node-mapping.md). Do not invent extra Executors and do not silently merge nodes outside of the explicitly allowed Collapsing Patterns.
11. **Wire the workflow inside a `create_workflow()` factory function** using `WorkflowBuilder`. The edges you add MUST exactly match the edges listed in the Phase 1 mapping table. Executor instantiation and `WorkflowBuilder.build()` must happen inside this function — not at module level — so each call returns a fresh, independent workflow instance:
    - `.add_edge(source, target)` for linear connections
    - `.add_edge(source, target, condition=fn)` for conditionals (one per PF `activate_config`, with semantically identical predicate)
    - `.add_fan_out_edges(source, [targets])` for parallel branches (preserve PF parallelism — never serialize)
    - `.add_fan_in_edges([sources], target)` for aggregation
12. **Handle LLM nodes**:
    - Extract system prompt from `.jinja2` template → `Agent(instructions="...")`
    - Pick the right client — see [references/workflow-context.md](references/workflow-context.md)
    - `Agent.run()` returns an `AgentResponse` — extract text with `.text`
    - **Preserve LLM parameters** — pass `temperature`, `max_tokens`, etc. via `OpenAIChatOptions` (see [references/workflow-context.md](references/workflow-context.md))
13. **Handle chat history** — format prior turns into a prompt string in an InputExecutor, not as raw message dicts.
14. **Handle Python tool nodes** — convert to plain functions and pass to `Agent(tools=[fn])`.
15. **For evaluation flows / multimodal flows / custom-tool nodes** — follow the topic file you loaded in Phase 1 step 5.

### Phase 3 — Generate Supporting Files

16. **`requirements.txt`** — include only needed `agent-framework-*` packages. Add `azure-identity>=1.15.0` if any LLM client uses the identity template.
17. **`.env.example`** — template with required environment variables (endpoint, model, key only if the connection uses key auth).
18. **`test_<name>.py`** — runnable sample script exercising single-turn and multi-turn (if applicable).
19. **`README.md`** — brief setup and run instructions. (Other documentation only if the user requests it.)

### Phase 4 — Validate

20. **Create a virtual environment** and install dependencies.
21. **Run the test sample** to verify the workflow produces output.
22. **Verify graph topology equivalence against `flow.dag.yaml`** — re-open the source `flow.dag.yaml` and the Phase 1 mapping table, then check:
    - [ ] Every PF node appears in the mapping table and is realized as exactly one MAF Executor (or is part of an explicitly annotated Collapsing Pattern).
    - [ ] No MAF Executor exists that does not correspond to a PF node or an annotated merge.
    - [ ] Every PF `${node.output}` reference is realized as a MAF edge between the corresponding Executors.
    - [ ] No MAF edges exist that are not present in PF.
    - [ ] PF parallel branches use `add_fan_out_edges`; PF fan-in points use `add_fan_in_edges`. No parallel branch has been serialized.
    - [ ] Every PF `activate_config` has a matching `add_edge(..., condition=fn)` whose predicate is semantically identical (same truth value for the same inputs).

    If any check fails, fix the workflow before proceeding.
23. **Fix errors** — see [references/gotchas.md](references/gotchas.md).

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
│   └── evaluation-flows.md        ← aggregation: true + EvalRunner pattern
├── templates/
│   └── eval_runner.py             ← Reusable runner — copy verbatim into eval flow output
└── examples/
    ├── linear-chat.md             ← Single LLM node + chat history
    ├── multimodal-chat.md         ← Image inputs (GPT-4V style)
    └── evaluation.md              ← Per-row workflow + aggregation function + run_eval.py
```

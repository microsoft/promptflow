---
name: maf-prs-job
description: "Convert an existing Prompt Flow Parallel Run Step (PRS) pipeline submission into an Azure ML PRS pipeline that runs a Microsoft Agent Framework (MAF) workflow. Wraps the MAF workflow into a PRS init()/run() entry script, generates the parallel component YAML and conda environment, and rewrites the pipeline submission script. Replaces what `load_component(flow.dag.yaml)` did automatically for Prompt Flow \u2014 produces the hand-built equivalent so that downstream pipeline code (`flow_node = flow_component(...)`, `flow_node.outputs.flow_outputs`, `flow_node.outputs.debug_info`, `flow_node.mini_batch_size`, scheduler, batch endpoint) stays unchanged. WHEN: convert promptflow PRS to MAF PRS, migrate PRS pipeline to agent framework, wrap MAF workflow as parallel component, bulk run MAF workflow, run agent framework as parallel run step, batch run MAF workflow on AML, submit MAF workflow as pipeline component, replace flow.dag.yaml with MAF workflow in pipeline, load_component equivalent for MAF workflow, MAF version of flow_component, load MAF workflow as component, wrap MAF workflow as flow component, MAF flow component, replace flow_node in pipeline with MAF workflow, keep flow_outputs and debug_info ports with MAF, MAF parallel component with connections={}, run MAF workflow as flow_node in AML pipeline, load_component('workflow.py') doesn't work. DO NOT USE FOR: converting the flow itself (use promptflow-to-maf), deploying as online endpoint (use maf-online-endpoint), enabling tracing only (use maf-tracing)."
license: MIT
metadata:
  author: Team
  version: "0.1.0-draft"
---

# Prompt Flow PRS → MAF PRS Pipeline Conversion

> Convert an existing **Prompt Flow Parallel Run Step (PRS)** pipeline submission
> (one that uses `load_component("flow.dag.yaml")`) into a PRS pipeline that
> runs a **Microsoft Agent Framework (MAF) workflow** as the parallel component.
>
> What `load_component(flow.dag.yaml)` did automatically — and which pieces
> this skill produces by hand — is documented in
> [references/pf-vs-maf-prs.md §0](references/pf-vs-maf-prs.md).

## Triggers

Activate this skill when the user wants to:

- Convert a Prompt Flow PRS pipeline submission to use a MAF workflow instead.
- Run a MAF workflow as a parallel / bulk job on AML compute.
- Replace `load_component(flow.dag.yaml)` with a hand-built parallel component
  that wraps a MAF workflow.

Also activate on these PF-user phrasings (people who learned from the
[run-flow-with-pipeline notebook](../../../examples/tutorials/run-flow-with-pipeline/pipeline.ipynb)
will describe their need in PF terms):

- "How do I `load_component` a MAF workflow?" / "`load_component('workflow.py')`
  doesn't work — what's the right way?"
- "Give me the MAF equivalent of `flow_component = load_component('flow.dag.yaml')`."
- "Wrap my MAF workflow as a **flow component** / **parallel component** /
  **PF-style component**."
- "I want to use my MAF workflow as `flow_node` in my existing AML pipeline."
- "My pipeline does `result_parser_node(pf_output_data=flow_node.outputs.flow_outputs,
  pf_debug_data=flow_node.outputs.debug_info)` — keep that working with MAF."
- "How do I pass `connections={...}` / `${data.url}` column mapping when the
  step is a MAF workflow instead of a flow?"

In all of these cases the user's mental model is the PF auto-converted **flow
component** with predefined `data` / `flow_outputs` / `debug_info` ports.
This skill produces the hand-built MAF equivalent and **preserves those names**
so downstream pipeline DSL, scheduler, and batch-endpoint code copy-paste
unchanged.

Do **not** use this skill to convert the `flow.dag.yaml` itself — that is the
job of [promptflow-to-maf](../promptflow-to-maf/SKILL.md). This skill assumes
the MAF workflow already exists (or will be produced by `promptflow-to-maf`)
and only deals with the **PRS / pipeline plumbing** around it.

---

## Outputs

For an input project containing a MAF workflow (`workflow.py` exporting
`create_workflow()`) and an existing PF PRS submission script, **add the
PRS plumbing into the MAF workflow folder itself** (default — keeps
`workflow.py` and its deployment package together so customers manage one
folder per workflow):

```
<maf-workflow-folder>/
├── workflow.py               ← existing MAF workflow (untouched)
├── requirements.txt          ← existing (untouched)
├── src/                      ← ADDED: PRS entry + plumbing
│   ├── entry.py              ← thin PRS wrapper: init / run(mini_batch, context) / shutdown
│   ├── hooks.py              ← THE ONLY USER-EDITED FILE: setup / build_workflow_input / serialize_output
│   └── maf_prs/              ← generic plumbing (mirrors promptflow-parallel's processor/executor split)
│       ├── __init__.py
│       ├── config.py         ← argparse → MafPrsConfig
│       ├── executor.py       ← per-row driver; calls into hooks.py
│       └── processor.py      ← mini-batch dispatch, event-loop reuse, finalize
├── component.yaml            ← ADDED: Azure ML parallel component (replaces flow.dag.yaml)
├── env/
│   └── conda.yml             ← ADDED: runtime env (agent-framework + AML PRS deps)
├── submit_pipeline.py        ← ADDED: MLClient + @pipeline DSL submission driver
└── data/sample.jsonl         ← ADDED only when the source `Input(path=...)` is a local file the agent can read; reused verbatim for cloud paths
```

The **original PF flow folder is never modified** (it's a separate
folder). Existing files in the MAF folder (`workflow.py`,
`requirements.txt`, tests, …) are also left untouched — only **new**
files are added next to them.

The only file the user normally needs to edit after generation is
`src/hooks.py` — `build_workflow_input(row)`, `serialize_output(output)`,
and the optional `setup(config)` — and even those are auto-filled when
the source provides enough information (see
[auto-derive-checks.md](references/auto-derive-checks.md)).
`maf_prs/executor.py` and the rest of the package are **generic** and can
be vendored unchanged across all converted workflows.

### Alternative: sibling folder layout (opt-in)

If the user explicitly asks to keep the MAF folder pristine (e.g. it is a
public doc sample), generate a sibling folder named
`<maf-workflow-folder>-prs/` instead, and **copy** `workflow.py` into it
so `code: ./` in `component.yaml` ships it to AML. Trade-off: duplicate
`workflow.py` to keep in sync. Default to the consolidated layout above
unless asked.

---

## Core Rules

1. **Read both sides first.** Parse the user's PF PRS submission (script
   or notebook cells) and the MAF workflow (`workflow.py`, must export
   `create_workflow()`). If `create_workflow()` is missing, route the user
   to [promptflow-to-maf](../promptflow-to-maf/SKILL.md) first.
2. **Auto-fill only when the source is unambiguous.** Run the checks in
   [auto-derive-checks.md](references/auto-derive-checks.md) and emit
   generated code only for fields that pass. For everything else leave a
   `# TODO` stub that quotes the original PF source and the missing piece —
   **never invent endpoint URLs, data paths, or untyped handler inputs**.
3. **One workflow instance per row.** MAF workflows do not support
   concurrent `run()` on the same instance. The template
   `executor.execute(...)` builds a fresh workflow per row from the cached
   `_create_workflow` factory; do not "optimise" by caching an instance.
4. **One asyncio loop per worker.** `processor.init()` creates the loop;
   `process()` reuses it via `run_until_complete`; `finalize()` closes it.
   Do not call `asyncio.run()` per row — it leaks Azure SDK transports.
5. **Preserve PRS contract.** `entry.py` exposes exactly three top-level
   functions: `init()`, `run(mini_batch, context)`, `shutdown()`.
   `context.global_row_index_lower_bound` is required to stamp a stable
   `line_number` on each result; downstream PF eval tooling joins inputs
   to outputs by it.
6. **Mirror PRS run settings 1:1.** Every PF PRS knob has an exact AML
   parallel-component equivalent; carry values across unchanged unless the
   user asks otherwise. See
   [pf-vs-maf-prs.md §4](references/pf-vs-maf-prs.md) for the table.
7. **`connections=` → component inputs + Managed Identity.** Surface
   endpoint URL / deployment / API version as component `inputs:`, pass
   them via `program_arguments`. Prefer Managed Identity + Key Vault for
   secrets; never hard-code keys in `component.yaml`.
8. **Generated project must be self-contained.** Whether using the
   default consolidated layout (PRS files added to the MAF folder) or the
   sibling-folder layout, no path should refer back to the original PF
   flow folder. Copy data samples, prompt files, and any user packages
   the workflow imports. In sibling-folder mode, also copy `workflow.py`
   so AML's `code:` snapshot ships it.

---

## Workflow

A single five-step loop. Each step combines the **decision** (what to
ask / what to print to the user) with the **action** (what to write).

### 1. Ask

Use `vscode_askQuestions` for any of the following that are not obvious
from the workspace:

- Path to the existing PF PRS submission (script or notebook cell).
- Path to the MAF workflow (`workflow.py` with `create_workflow()`).
- Whether the workflow has been migrated yet — if not, route to
  [promptflow-to-maf](../promptflow-to-maf/SKILL.md) first.

### 2. Audit

Extract the PRS settings from the source script using the table in
[pf-vs-maf-prs.md §4](references/pf-vs-maf-prs.md) (compute,
mini_batch_size, retry_settings, etc.) and **show the populated table to
the user** before continuing.

### 3. Decide (Phase 1.5)

Run the checks in
[auto-derive-checks.md](references/auto-derive-checks.md) (A–J) and
**print the verdict table** showing which fields will be auto-filled vs.
left as TODO. The same table doubles as the change log handed to the user
in step 5.

### 4. Generate

Add `assets/` files **into the MAF workflow folder** (default) or into a
new sibling `<maf-workflow-folder>-prs/` (only if the user opted in).
Do not overwrite any pre-existing file in the MAF folder; if a file name
already exists (e.g. `submit_pipeline.py`), confirm with the user before
overwriting.

| File(s) | Action |
|---|---|
| `src/entry.py` | Copy verbatim. Do **not** edit. |
| `src/maf_prs/{__init__,config,processor,executor}.py` | Copy verbatim. Do **not** edit unless the workflow needs an extra component input (then add a flag in `config.parse_args` and surface it in `component.yaml`). |
| `src/hooks.py` | Apply auto-derived bodies for `build_workflow_input` / `serialize_output` per the verdict table; insert TODO stubs (template in [auto-derive-checks.md](references/auto-derive-checks.md)) where checks failed. If component inputs need to be turned into env vars / file paths before the workflow imports, fill the `setup(config)` body too. Add the matching `from workflow import ...` line at the top. |
| `component.yaml` | Fill `inputs:` from check F; fill PRS settings from the audit table; set `program_arguments` to forward inputs + `--output_dir ${{outputs.debug_info}}`. Use `code: ./` and `entry_script: src/entry.py` so `workflow.py` (sibling of `src/`) is shipped to AML. **Set `data` input `type: uri_file`** and **always include the PF compatibility flag set** in `program_arguments` (`--amlbi_pf_enabled True --amlbi_pf_run_mode component --amlbi_file_format jsonl --amlbi_mini_batch_rows 1`) — PRS rejects bare `uri_file` without these flags (gotcha #12). **Wrap every `optional: true` input in `$[[--flag ${{inputs.X}}]]`** in `program_arguments` — bare `${{inputs.X}}` for an optional input fails registration with `Optional input X must be placed in nested argument: $[[]]` (gotcha #15). **Do not** add `--pf_input_*` flags. |
| `env/conda.yml` | Add any extra pip packages imported by the workflow, **always with a lower-bound version pin** (`package>=X.Y.Z`) — bare entries trigger `error: resolution-too-deep` on the AML image build host and the job never reaches `init()` (gotcha #14). Keep the existing PRS runtime pins as-is. |
| `submit_pipeline.py` | Fill `data_input` (check H) by **preserving the source `Input(path=..., type=..., mode=...)` verbatim** — same path, same type, same mode. Only rewrite the path to `data/sample.jsonl` if you also copied it locally per the rule below. Fill `MODEL_ENDPOINT` / `MODEL_DEPLOYMENT` (check G), and run-settings assignments. **Do not** pass `${data.col}` arguments. |
| `data/sample.jsonl` | **Only** copy from the source `Input(path=...)` when (a) it points at a local file the agent can read, **and** (b) the user did not explicitly ask to keep the original input. For remote / `azureml://` / `Input(...)` already pointing at a workspace data asset, leave the source `Input(...)` unchanged in `submit_pipeline.py` and skip this file (do not invent a sample). Print a one-line note in the verdict table either way. |
| `workflow.py` | **Default (consolidated):** already present in the target folder — do nothing. **Sibling-folder mode only:** copy from the source MAF folder. |

### 5. Validate & hand off

If no input-side TODO remains **and** a local jsonl file is available
(either copied as `data/sample.jsonl` or already pointed at by the source
`Input(path=...)`), run the local dry-run from the target folder:

```bash
cd <maf-workflow-folder>   # or <maf-workflow-folder>-prs in sibling mode
python -c "
import pandas as pd
from types import SimpleNamespace
import sys; sys.path.insert(0, 'src')
from entry import init, run, shutdown
init()
ctx = SimpleNamespace(minibatch_index=0, global_row_index_lower_bound=0)
print(run(pd.read_json('<path-to-local-jsonl>', lines=True), ctx))
shutdown()
"
```

If the source `Input(path=...)` is a remote URI (datastore / data asset)
**and** no local sample exists, **skip the dry-run** and tell the user
the project will be exercised on the first AML submission instead.

If TODOs remain, skip the dry-run and tell the user which file to edit
first. If the dry-run fails, consult
[references/gotchas.md](references/gotchas.md), fix, retry.

Hand off `python submit_pipeline.py` with: the verdict table from step 3,
the exact command to run, and a one-line description of what to look for
in the streamed log (one JSONL row per input row in
`outputs.flow_outputs/parallel_run_step.jsonl`).

---

## Related Skills

- [promptflow-to-maf](../promptflow-to-maf/SKILL.md) — convert the flow itself
  (run **before** this skill if not already done).
- [maf-online-endpoint](../maf-online-endpoint/SKILL.md) — online (real-time)
  deployment of a MAF workflow. Use for request/response semantics rather
  than batch.
- [maf-tracing](../maf-tracing/SKILL.md) — enable Application Insights tracing
  (`maf_prs/executor.py::_setup_tracing` already wires it up when
  `APPLICATIONINSIGHTS_CONNECTION_STRING` is set).

## References

- [pf-vs-maf-prs.md](references/pf-vs-maf-prs.md) — side-by-side mapping
  (PF auto-component → MAF hand-built) + PRS run-settings table.
- [auto-derive-checks.md](references/auto-derive-checks.md) — the 10
  Phase 1.5 checks (A–J) + TODO stub template + verdict table format.
- [gotchas.md](references/gotchas.md) — async loop reuse, mini-batch retry
  semantics, MSI / connection mapping, common dry-run failures.

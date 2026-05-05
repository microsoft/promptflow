# Wrapping a MAF Workflow as an Azure ML Parallel Component

This sample wraps [`phase-2-rebuild/01_linear_flow.py`](../../phase-2-rebuild/01_linear_flow.py)
as an **Azure ML Parallel Component** (PRS — Parallel Run Step), so you can
batch-run the workflow over a JSONL input file and get one JSONL output row
per input row.

This is the MAF equivalent of what `load_component(flow.dag.yaml)`
auto-generated for Prompt Flow PRS jobs.

## Files

| File | Purpose |
|------|---------|
| [`component.yaml`](component.yaml) | Parallel component spec (replaces `flow.dag.yaml`) |
| [`env/conda.yml`](env/conda.yml) | Runtime conda env (MAF + AML PRS deps) |
| [`src/entry.py`](src/entry.py) | PRS `init` / `run(mini_batch, context)` / `shutdown` wrapper |
| [`src/hooks.py`](src/hooks.py) | Per-workflow customisation (row → input, output → JSON) |
| [`src/maf_prs/`](src/maf_prs/) | Generic plumbing — config, processor, executor |
| [`data/sample.jsonl`](data/sample.jsonl) | Sample input rows |
| [`submit_pipeline.py`](submit_pipeline.py) | `MLClient` + `@pipeline` DSL submission driver |

## How it wraps `01_linear_flow.py`

`01_linear_flow.py` exports a module-level `workflow` object whose start
executor's handler signature is `receive(self, question: str, ...)`.

The PRS wrapper plumbs this together as follows:

1. **Per-row factory.** `executor.py` calls
   [`workflow_loader.load_workflow()`](../../workflow_loader.py) for every
   row. `load_workflow()` re-imports the workflow file via `importlib.util`,
   producing a fresh `workflow` instance per row — required because MAF
   workflows do not support concurrent `run()` on the same instance.
2. **Row → workflow input.** [`src/hooks.py::build_workflow_input`](src/hooks.py)
   maps each `{"question": "..."}` row to the string `question` the start
   executor expects.
3. **Workflow output → JSON.** [`src/hooks.py::serialize_output`](src/hooks.py)
   unwraps the `AgentRunResponse` returned by the LLM executor to its
   `.text`, so PRS can append it as a JSONL line to `flow_outputs`.

To wrap a different workflow, change `--maf_workflow_file` in
[`component.yaml`](component.yaml) and edit
[`src/hooks.py`](src/hooks.py).

## Generating this scaffolding for your own flow (`maf-prs-job` skill)

This sample was hand-built for the linear flow. For a real Prompt Flow PRS
job, the [`maf-prs-job`](../../../../.github/skills/maf-prs-job/SKILL.md)
skill regenerates the same scaffolding (component spec, conda env, entry
script, processor/executor, hooks, submission driver) tailored to your
flow — you only edit `src/hooks.py` afterwards.

### When to use the skill

Use it when you have **either**:

- An existing PF PRS submission script (a `.py` or notebook cell that
  calls `load_component("flow.dag.yaml")` and wires the component into a
  pipeline), and you want to keep the pipeline plumbing but swap the
  per-row task to a MAF workflow.
- An already-migrated MAF workflow folder that exports
  `create_workflow()` (or a single-file workflow like
  [`01_linear_flow.py`](../../phase-2-rebuild/01_linear_flow.py)) and you
  want it submittable as a parallel job on AML.

If your flow has not been migrated yet, run the
[`promptflow-to-maf`](../../../../.github/skills/promptflow-to-maf/SKILL.md)
skill **first** to produce the workflow file, then this one.

### How to invoke it

In Copilot Chat, point at both sides of the migration so the skill can
auto-derive the row-mapping and pipeline settings:

```
Use the maf-prs-job skill to wrap
  examples/flows/standard/web-classification-maf/workflow.py
into a parallel pipeline. The original PF submission is at
  examples/tutorials/run-flow-with-pipeline/pipeline.py
```

The skill will:

1. **Audit** — parse the PF submission and print the run-settings table
   it lifted (`compute`, `mini_batch_size`, `retry_settings`, `connections`,
   …) so you can confirm before any files are written.
2. **Decide** — run its 10 auto-derive checks (A–J) and show a verdict
   table marking which fields it can fill from the source vs. which it
   leaves as `# TODO` stubs in `src/hooks.py`.
3. **Generate** — drop the same files this sample contains
   (`component.yaml`, `env/conda.yml`, `src/entry.py`, `src/hooks.py`,
   `src/maf_prs/`, `submit_pipeline.py`) into your MAF workflow folder
   (consolidated layout, default) or into a sibling `<folder>-prs/`
   (opt-in). `workflow.py` and `requirements.txt` are not touched.
4. **Validate** — if a local jsonl sample is available, run the same
   `dryrun.py`-style smoke test before handing back the
   `python submit_pipeline.py` command.

### What the skill produces vs. what's in this sample

| File | This sample (hand-built) | Skill output |
|---|---|---|
| `component.yaml` | Hard-codes `--maf_workflow_file phase-2-rebuild/01_linear_flow.py` | Surfaces real `connections=` from PF as typed component inputs (e.g. `model_endpoint`, `model_deployment`) |
| `src/hooks.py` | Maps the single `question` field → `str` input | Auto-fills `build_workflow_input` from the PF input mapping + your start handler signature; leaves a `# TODO` stub when the source is ambiguous |
| `submit_pipeline.py` | Loads `data/sample.jsonl` from this folder | Preserves the source `Input(path=..., type=..., mode=...)` verbatim — same data asset, no invented sample |
| `src/maf_prs/`, `src/entry.py` | Identical | Identical (vendored verbatim) |

The generic plumbing (`src/maf_prs/{config,executor,processor}.py` and
`src/entry.py`) is exactly the same in both — the skill never touches it
unless your workflow needs an extra component input.

### Skill references worth reading

- [`SKILL.md`](../../../../.github/skills/maf-prs-job/SKILL.md) — the
  five-step generation loop and the file-action table.
- [`references/pf-vs-maf-prs.md`](../../../../.github/skills/maf-prs-job/references/pf-vs-maf-prs.md) —
  side-by-side mapping of every PF PRS knob to its AML equivalent (the
  source for the run-settings table further down this README).
- [`references/auto-derive-checks.md`](../../../../.github/skills/maf-prs-job/references/auto-derive-checks.md) —
  what the skill can and cannot infer automatically.
- [`references/gotchas.md`](../../../../.github/skills/maf-prs-job/references/gotchas.md) —
  the 16 issues you're likely to hit (most relevant: #12 `uri_file`
  compat flags, #14 `setuptools<80`, #15 `resolution-too-deep`,
  #16 `$[[]]` for optional inputs).

## Local dry-run (no AML compute)

Activate the workspace `.venv-af` and install the small extra packages PRS
expects (only needed locally — the conda env on AML already has them):

```powershell
# from the repo root
.\.venv-af\Scripts\Activate.ps1
pip install pandas
```

Set Foundry credentials so the workflow can call the model:

```powershell
$env:FOUNDRY_PROJECT_ENDPOINT = "https://<account>.services.ai.azure.com/api/projects/<project>"
$env:FOUNDRY_MODEL            = "gpt-4o"
```

Run the dry-run from this folder:

```powershell
cd migration-guide/PromptFlow-to-MAF/phase-4-migrate-ops/4d-pipelines
python dryrun.py
```

You should see one JSONL line per input row, each containing the
`line_number`, the original `input`, and the model's `output`. The script
uses [`dryrun.py`](dryrun.py), which exercises the same
`init` / `run(mini_batch, context)` / `shutdown` contract that AML PRS
calls on [`src/entry.py`](src/entry.py).

## Submit to Azure ML

Prerequisites:

- An Azure ML workspace and a CPU compute cluster (default name
  `cpu-cluster`; override with `$env:AML_COMPUTE`).
- The compute identity has the `Cognitive Services User` role on the
  Foundry resource (see [`../4b-deployment/managed_identity.md`](../4b-deployment/managed_identity.md)).
- `azure-ai-ml` installed locally (the parity-check venv has it; otherwise
  `pip install azure-ai-ml`).

Submit:

```powershell
$env:SUBSCRIPTION_ID         = "<sub>"
$env:RESOURCE_GROUP          = "<rg>"
$env:WORKSPACE_NAME          = "<ws>"
$env:FOUNDRY_PROJECT_ENDPOINT = "https://<account>.services.ai.azure.com/api/projects/<project>"
$env:FOUNDRY_MODEL            = "gpt-4o"
$env:AML_COMPUTE              = "cpu-cluster"

python submit_pipeline.py
```

The submission script streams the run log. When it finishes, the appended
output file (`outputs.flow_outputs/parallel_run_step.jsonl`) has one JSON
line per input row, in the same order as `data/sample.jsonl`.

## How the run-settings map to Prompt Flow PRS

| Prompt Flow PRS setting | Equivalent in this sample | Where |
|---|---|---|
| `flow_node.compute` | `workflow_node.compute` | [`submit_pipeline.py`](submit_pipeline.py) |
| `flow_node.resources` | `workflow_node.resources` | [`submit_pipeline.py`](submit_pipeline.py) |
| `flow_node.mini_batch_size` | `workflow_node.mini_batch_size` / `mini_batch_size` in YAML | [`component.yaml`](component.yaml) |
| `flow_node.max_concurrency_per_instance` | same key, both files | [`component.yaml`](component.yaml) |
| `flow_node.retry_settings` | `retry_settings` | [`component.yaml`](component.yaml) |
| `flow_node.error_threshold` / `mini_batch_error_threshold` | same keys | [`component.yaml`](component.yaml) |
| `flow_node.logging_level` | `logging_level` | [`component.yaml`](component.yaml) |
| `flow_node(connections={...})` | env vars on the component node | [`submit_pipeline.py`](submit_pipeline.py) |
| `flow.dag.yaml` `inputs:` | `inputs:` block + `hooks.build_workflow_input` | [`component.yaml`](component.yaml), [`src/hooks.py`](src/hooks.py) |
| `flow.dag.yaml` `outputs:` | `flow_outputs` (jsonl) + `debug_info` (folder) | [`component.yaml`](component.yaml) |

## Why the four `--amlbi_pf_*` flags?

PRS's public schema only declares `mltable` and `uri_folder` as supported
input types, but its runtime also accepts `uri_file` when the four flags

```
--amlbi_pf_enabled True
--amlbi_pf_run_mode component
--amlbi_file_format jsonl
--amlbi_mini_batch_rows 1
```

are passed in `program_arguments`. Prompt Flow's runtime emits the same
flag set when `load_component(flow.dag.yaml)` builds the parallel
component; we replicate it so callers can pass a plain `.jsonl` file with
no MLTable spec required.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `RequireMLTablePackageException` on every mini-batch | `pkg_resources` import fails because setuptools 80+ removed it | Keep `setuptools<80` in [`env/conda.yml`](env/conda.yml) |
| `MAF workflow file not found` | `--maf_workflow_file` path is relative to the AML code snapshot root | Use a path relative to the migration-guide root, e.g. `phase-2-rebuild/01_linear_flow.py` |
| `RuntimeError: This workflow is already running` | Cached workflow instance reused across rows | Don't cache — `executor.py` calls `load_workflow()` per row |
| `401 PermissionDenied` from Foundry | Compute identity missing RBAC | Assign `Cognitive Services User` on the Foundry resource |

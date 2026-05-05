# MAF PRS — Common Gotchas

> Read this when something fails during local dry-run (Phase 3) or when the
> first AML submission fails (Phase 4). Ordered by frequency.

## 1. `RuntimeError: Workflow is already running`

**Cause:** A single MAF workflow instance was reused across rows or across
`run()` calls.

**Fix:** Build the workflow inside `MafWorkflowExecutor.execute(row, ...)`
(per-row) — never cache `self._workflow = create_workflow()` in
`executor.init()`. The template `executor.py` only caches the **factory**
(`self._create_workflow`), not an instance; if you removed that distinction
for "performance", put it back.

## 2. `RuntimeError: There is no current event loop in thread 'Dummy-N'`

**Cause:** PRS spawns worker threads/processes; the loop created in `init()`
on one thread is not visible to another.

**Fix:** The template `processor.init()` uses `asyncio.new_event_loop()` +
`asyncio.set_event_loop(loop)`, and `processor.process()` calls
`self._loop.run_until_complete(...)`. Do not switch to `asyncio.run(...)` —
it creates and tears down a loop per call, which leaks transports inside many
Azure SDK clients. `processor.finalize()` closes the loop on shutdown.

## 3. `ImportError: cannot import name 'create_workflow' from 'workflow'`

**Cause:** Either the workflow file does not export a factory, or
`component.yaml` is not set up so the workflow ends up on `sys.path`.

**Fix:**
- Confirm `workflow.py` exports `create_workflow()` (this is also a
  `promptflow-to-maf` rule — see rule 11 of that skill).
- The template `executor.init()` does `sys.path.insert(0, working_dir)` and
  `entry.init()` passes `Path(__file__).resolve().parents[1]` as the working
  dir, on the assumption that the project layout is `<root>/src/entry.py`,
  `<root>/src/hooks.py`, `<root>/src/maf_prs/...`, and `<root>/workflow.py`.
  If you flatten the layout, update the `parents[N]` index in `entry.py`.
- `component.yaml` must use `code: ./` and `entry_script: src/entry.py`
  (not `code: ./src`) so the project root — which contains `workflow.py`
  alongside `src/` — is uploaded to AML. AML packages whatever directory
  `code:` points to and uploads it as the task code; files **outside**
  that directory are not shipped, so `code: ./src` would leave
  `workflow.py` behind.
- This works for both supported layouts:
  * **Consolidated** (default): the PRS files (`src/`, `component.yaml`,
    …) live inside the existing MAF workflow folder, next to the
    workflow's own `workflow.py`.
  * **Sibling** (`<maf-folder>-prs/`): `workflow.py` is **copied** into
    the new folder so `code: ./` ships it.

## 4. PRS retries the whole mini-batch on a single bad row

**Cause:** The default behaviour: if `run()` raises, PRS retries the entire
mini-batch (matches PF semantics).

**Fix:**
- The template `executor.execute(...)` catches per-row exceptions and records
  them in the result dict so a single bad row does not poison the batch. If
  you want PRS to retry on transient errors, **re-raise** specific exception
  types (e.g. throttling 429 from the LLM) inside `execute()`.
- Tune `mini_batch_size` down to keep retry cost small.
- Use `error_threshold` (per-row) and `mini_batch_error_threshold` to bound
  total failures before aborting the job. `-1` disables both.

## 5. Output JSONL has wrong number of rows

**Cause:** `run()` returned fewer or more entries than `len(mini_batch)`.

**Fix:** PRS expects one entry per input row. The template
`processor.process()` returns `asyncio.gather(*per_row)` which preserves
order and length. If you do any filtering inside `executor.execute`, return
a placeholder dict (e.g. `{"line_number": n, "input": row, "output": None,
"skipped": True}`) instead of dropping rows.
## 6. `azure.identity.CredentialUnavailableError` on AML compute

**Cause:** The compute does not have a Managed Identity assigned, or the
identity lacks the role on the LLM endpoint resource.

**Fix:**
- Assign a Managed Identity to the AML compute cluster (system-assigned is
  simplest).
- Grant it `Cognitive Services OpenAI User` (or equivalent Foundry role) on
  the AI Services resource scope.
- Do **not** ship API keys via `program_arguments` — they end up in job
  metadata and logs.

## 7. `pip` install fails on `agent-framework` inside the PRS env

**Cause:** Wrong Python version or missing build deps.

**Fix:**
- Pin `python=3.11` in `conda.yml` (default in the template). MAF supports
  3.10+ but 3.11 is the safest match for current `agent-framework` wheels.
- Use the `mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04:latest` base
  image (default in the template) — it has `gcc` available for any wheels
  that need to compile.

## 8. "No outputs produced" on every row

**Cause:** `result.get_outputs()` returned `[]` because the workflow only
emits intermediate events, not a final `WorkflowOutputEvent`.

**Fix:** Confirm the workflow's last executor calls
`ctx.set_output(...)` or yields a `WorkflowOutputEvent`. If the workflow
streams text instead, switch `executor.execute` to use `workflow.run_stream(...)`
and aggregate `AgentRunUpdateEvent` deltas before serialising.

## 9. Mini-batch shape mismatch (DataFrame vs. file list)

**Cause:** `entry.py` was tested against a jsonl file but the component is
fed a `uri_folder` of opaque files (or vice versa).

**Fix:** The template `processor._iter_rows()` handles both shapes. If you
customised it, make sure both branches are tested. As a quick check, log
`type(mini_batch).__name__` at the top of `processor.process()`.

## 10. Job runs locally but hangs on AML

**Cause:** The workflow is making an outbound call that the AML compute
network policy blocks (e.g. private-endpoint-only Foundry resource, missing
DNS zone link, or NSG denial).

**Fix:** This is an Azure networking issue, not a MAF issue. Verify with
`az network watcher test-connectivity` from a debug pod on the cluster, or
attach Application Insights tracing (`executor._setup_tracing` already wires
it up if `APPLICATIONINSIGHTS_CONNECTION_STRING` is set as a deployment env
var) and look for connection timeouts.

## 11. `line_number` missing from output rows (breaks downstream PF eval)

**Cause:** `entry.run()` was defined as `def run(mini_batch):` (one
parameter) instead of `def run(mini_batch, context):`. Without `context`
the processor cannot read `global_row_index_lower_bound`, so `line_number`
falls back to `0` for every mini-batch — batch-eval tools that join
input rows to output rows by `line_number` will silently produce wrong
results.

**Fix:** Keep the template `run(mini_batch, context)` signature. PRS
always passes both arguments; the second was optional only in very old
PRS runtime versions.

## 12. `ArgumentException: Input format UriFile is not supported.`

**Cause:** The pipeline's `data` Input was declared as
`Input(type=AssetTypes.URI_FILE, ...)` and `program_arguments` does not
carry the PF compatibility flag set, so PRS's
`ArgValidator._assert_uri_file_enabled` rejects `uri_file` at boot.

**The PRS runtime, however, has an undocumented compatibility mode** that
PF used to ship `uri_file` jsonl inputs. When the parallel component's
`program_arguments` carries the **PF compatibility flag set**, PRS:

1. Skips the `uri_file` validator gate.
2. Parses the jsonl file line-by-line and dispatches **`list[dict]`**
   row mini-batches into `entry.run(mini_batch, context)`.
3. Reads each returned JSON string and writes only the `output` field
   into `parallel_run_step.jsonl` (matching PF's "your flow's output IS
   the row output" semantic).

**Fix (default for this skill):** add the four flags below to
`component.yaml::task.program_arguments` and set `data.type: uri_file`:

```yaml
inputs:
  data:
    type: uri_file
    description: Single jsonl file; PRS parses each line into a row dict.

task:
  program_arguments: >-
    --amlbi_pf_enabled True
    --amlbi_pf_run_mode component
    --amlbi_file_format jsonl
    --amlbi_mini_batch_rows 1
    --output_dir ${{outputs.debug_info}}
```

| Flag | Effect |
|---|---|
| `--amlbi_pf_enabled True` | Flips PRS's ArgValidator gate so `type: uri_file` is accepted. |
| `--amlbi_pf_run_mode component` | PF "I am a flow component" signal; PRS extracts the `output` field from each returned JSON string into the appended jsonl line. |
| `--amlbi_file_format jsonl` | PRS parses the input file as jsonl and dispatches row dicts. Without it, `uri_file` → `list[file_path]` mini-batch (gotcha #9). |
| `--amlbi_mini_batch_rows 1` | Switch from file-count to row-count batching. Pair with `--amlbi_file_format`. |

In `submit_pipeline.py`:

```python
data_input = Input(
    path=str(HERE / "data" / "sample.jsonl"),  # or azureml://datastore/.../*.jsonl
    type=AssetTypes.URI_FILE,
    mode="mount",
)
```

`mini_batch_size: "5"` then means 5 rows per mini-batch.
`processor._iter_rows()` must handle the `list[dict]` shape (template
already does — see the `isinstance(item, dict)` branch).

**Caveats of relying on this flag set:**

- The flags live in PRS's runtime arg parser but are **not part of the
  public schema**. They have worked unchanged across multiple PRS
  releases (PF used them in production), but Microsoft does not publish
  an SLA for them.
- The output `parallel_run_step.jsonl` contains only the workflow output
  (extracted by PRS from each JSON line), not the full
  `{"line_number", "input", "output", "error"}` wrapper our `executor`
  returns. If downstream eval tooling needs the input echo or
  `line_number`, have `hooks.serialize_output` return a dict containing
  those fields.

**Alternative — file-list input (`uri_folder`):** keep `type: uri_folder`
in both `submit_pipeline.py` and `component.yaml`, and **drop the
`--amlbi_*` flags**. PRS will then dispatch each mini-batch as a
`list[str]` of file paths (gotcha #9), so `mini_batch_size` becomes
"files per batch" and `processor._iter_rows()` yields `{"path": ...}`
rows. Use this only when each row really is its own opaque file (e.g.
images, audio).

## 13. `EntryScriptException: No module named 'maf_prs'`

**Cause:** `component.yaml` uses `code: ./` + `entry_script: src/entry.py`
(needed so `workflow.py` ships with the snapshot — see gotcha #3). PRS
then uploads the project root and only puts the **project root** on
`sys.path`. The entry module is loaded as `src.entry`, and inside it
`from maf_prs.processor import create_processor` resolves `maf_prs` as a
top-level package — which doesn't exist (it's actually `src.maf_prs`).
Local dry-run masks this because we manually `sys.path.insert(0, 'src')`.

**Fix:** make `src/entry.py` add its own directory to `sys.path` **before**
the first `maf_prs` import. The template asset already does this:

```python
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from maf_prs.processor import create_processor  # noqa: E402
```

Do **not** "fix" this by switching to `from .maf_prs.processor import
create_processor` — PRS does not always load entry as part of a package,
so the relative import will fail in some PRS runtime versions. The
`sys.path` prepend is layout-agnostic and works in every PRS variant.

## 14. Image build aborts with `error: resolution-too-deep`

**Cause:** `env/conda.yml` lists pip dependencies without lower-bound
version pins (e.g. bare `azureml-core`, `pandas`, `azure-identity`). Modern
pip's resolver explores the version space exhaustively when there are no
constraints; the AML build host hits its built-in
`MAX_RESOLVER_DEPTH` and bails out before `conda env create` finishes.

The build log at `azureml-logs/20_image_build_log.txt` shows:

```
DownloadPip subprocess error:
error: resolution-too-deep

× Dependency resolution exceeded maximum depth
╰─> Pip cannot resolve the current dependencies as the dependency graph is
    too complex for pip to solve efficiently.

CondaEnvException: Pip failed
ERROR: failed to solve: process "/bin/sh -c ldconfig ... conda env create ..."
       did not complete successfully: exit code: 1
```

The job never reaches `init()` — the failure is purely an environment
build problem, even though the AML run UI lists it as a generic
"Image build failed".

**Fix:** Pin every pip entry in `env/conda.yml` with a lower bound
(`package>=X.Y.Z`). The skill's template `conda.yml` does this for every
package; if you add a new dependency, add a lower bound for it too.

```yaml
pip:
  - azureml-core>=1.59.0
  - azureml-mlflow>=1.59.0
  - azureml-dataset-runtime>=1.59.0
  - pandas>=2.2.0
  - agent-framework>=1.0.1
  - azure-identity>=1.19.0
  - azure-monitor-opentelemetry>=1.6.4
```

Upper bounds are not needed and can cause integrity-check failures with
the AML pre-installed packages — keep them open-ended.

## 15. `Optional input X must be placed in nested argument: $[[]]`

**Cause:** `component.yaml` declares an input as `optional: true` but
references it with a bare `${{inputs.X}}` placeholder in
`program_arguments`. AML refuses to register the component, with this
exact error from `managementfrontend`:

```
Error occurred when loading YAML file rootNode, details: Command "..."
has error:
Optional input X must be placed in nested argument: $[[]].
```

Optional inputs need the **nested-argument syntax** so PRS can omit the
flag entirely when the caller does not pass it (otherwise the flag would
appear with an empty value, which most argparse-based scripts treat as a
parse error).

**Fix:** Wrap the entire `--flag value` token in `$[[...]]`:

```yaml
inputs:
  api_version:
    type: string
    default: "2024-08-01-preview"
    optional: true

task:
  program_arguments: >-
    --model_endpoint ${{inputs.model_endpoint}}
    --model_deployment ${{inputs.model_deployment}}
    $[[--api_version ${{inputs.api_version}}]]
    --output_dir ${{outputs.debug_info}}
```

Required inputs (no `optional: true`) keep the bare `${{inputs.X}}`
form — only optional inputs need `$[[...]]`. If you would rather avoid
the special syntax, drop `optional: true` from the input declaration —
a `default:` is enough to make callers' lives easy without making the
input optional at the schema level.


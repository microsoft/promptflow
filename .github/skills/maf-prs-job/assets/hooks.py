"""
Per-workflow customisation hooks for the MAF PRS template.

This is the **only file most users need to edit**.  `executor.py` and the
rest of the `maf_prs/` package are generic plumbing and can be vendored
unchanged across all converted workflows.

Three hooks are exposed:

    setup(config)               -- one-time worker setup; translate component
                                   inputs (config.model_endpoint, etc.) into
                                   whatever environment the workflow expects
                                   (env vars, file paths, ...).  Default: no-op.

    build_workflow_input(row)   -- map one input row (dict) to the object the
                                   workflow's start executor expects.

    serialize_output(output)    -- convert the workflow's terminal output to a
                                   JSON-serialisable value that PRS will append
                                   to outputs.flow_outputs.

The skill agent fills `build_workflow_input` from the source PF mapping +
the workflow's start handler signature when both are unambiguous (see
auto-derive-checks.md A-D).  Otherwise it leaves a `# TODO` stub.

Imports of `workflow` work at module load because `executor.init()` adds
the project root to `sys.path` *before* importing this module.
"""
from __future__ import annotations

from typing import Any

# CUSTOMISE: import the typed input class(es) your workflow's start executor
# expects.  Leave commented out if the start handler accepts a free-form dict.
# from workflow import FlowInput


# ---------------------------------------------------------------------------
# CUSTOMISE #0: one-time worker setup
# ---------------------------------------------------------------------------
# Called once per worker process (after sys.path is wired up, before any
# row is processed).  Use this to translate component inputs into whatever
# the workflow needs at construction time.
#
# Examples:
#   if config.model_endpoint:
#       os.environ["AZURE_OPENAI_ENDPOINT"] = config.model_endpoint
#   if config.model_deployment:
#       os.environ["AZURE_OPENAI_DEPLOYMENT"] = config.model_deployment
# ---------------------------------------------------------------------------
def setup(config) -> None:
    return None


# ---------------------------------------------------------------------------
# CUSTOMISE #1: row -> workflow input
# ---------------------------------------------------------------------------
# `row` is the full mini-batch row as a dict.  Return whatever the workflow's
# first executor's @handler expects.
#
# Examples:
#   PF:  flow_node(url="${data.url}")
#   MAF: return row["url"]
#
#   PF:  flow_node(question="${data.q}", history="${data.history}")
#   MAF: return {"question": row["q"], "history": row["history"]}
#
#   PF:  (n/a -- workflow takes a typed object)
#   MAF: return FlowInput(url=row["url"])
# ---------------------------------------------------------------------------
def build_workflow_input(row: dict) -> Any:
    # Default: pass the entire row through.  Safe when the workflow's
    # first executor accepts a free-form dict; otherwise replace this.
    return row


# ---------------------------------------------------------------------------
# CUSTOMISE #2: workflow output -> JSON-serialisable value
# ---------------------------------------------------------------------------
# `output` is the last item of `WorkflowRunResult.get_outputs()`.  The
# default below duck-types the most common shapes (dicts, lists, primitives,
# objects with `.text`) and falls back to `str(output)`.  Override only if
# your workflow emits a custom payload that the duck-typed fallback mangles.
# ---------------------------------------------------------------------------
def serialize_output(output: Any) -> Any:
    if output is None:
        return None
    if isinstance(output, (dict, list, str, int, float, bool)):
        return output
    if hasattr(output, "text"):
        return output.text
    return str(output)

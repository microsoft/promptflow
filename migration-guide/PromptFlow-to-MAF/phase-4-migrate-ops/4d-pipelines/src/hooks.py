"""
Per-workflow customisation hooks for the MAF PRS sample wrapping
`phase-2-rebuild/01_linear_flow.py`.

This is the only file you typically need to edit when adapting the sample to
a different workflow. The other files in `maf_prs/` are generic plumbing.

Three hooks are exposed:

    setup(config)               -- one-time worker setup (env vars, etc.)
    build_workflow_input(row)   -- map one input row (dict) to the input the
                                   workflow's start executor expects.
    serialize_output(output)    -- convert the workflow's terminal output to
                                   a JSON-serialisable value.
"""
from __future__ import annotations

from typing import Any


def setup(config) -> None:
    """One-time worker setup. No-op for the linear flow sample."""
    return None


def build_workflow_input(row: dict) -> Any:
    """Map an input row to the workflow's start executor input.

    The linear flow's `InputExecutor.receive` handler signature is::

        async def receive(self, question: str, ctx: WorkflowContext[str]) -> None

    so we extract the `question` field from the row.
    """
    return row["question"]


def serialize_output(output: Any) -> Any:
    """Convert the workflow's terminal output to a JSON-serialisable value.

    The linear flow's `LLMExecutor` yields an `AgentRunResponse` (it has a
    `.text` attribute). We unwrap it to a plain string for JSONL output.
    """
    if output is None:
        return None
    if isinstance(output, (dict, list, str, int, float, bool)):
        return output
    if hasattr(output, "text"):
        return output.text
    return str(output)

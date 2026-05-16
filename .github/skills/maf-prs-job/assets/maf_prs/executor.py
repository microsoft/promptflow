"""
Per-row execution of a MAF workflow.  **Generic** — should not need editing.

Equivalent of promptflow-parallel's `ComponentRunExecutor`:
    PF                                       MAF (this file)
    -------------------------------          -------------------------------
    FlowExecutor.create(flow_dag, conns)     from workflow import create_workflow
    flow_executor.exec_line(inputs, index)   await workflow.run(hooks.build_workflow_input(row))
    FlowExecutor.apply_inputs_mapping        hooks.build_workflow_input(row)   ← in hooks.py
    persist_multimedia_data                  hooks.serialize_output(output)    ← in hooks.py

All per-workflow customisation lives in `src/hooks.py`.  This file only
provides the generic per-row driver.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from .config import MafPrsConfig

logger = logging.getLogger("maf-prs.executor")


class MafWorkflowExecutor:
    """Drives a MAF workflow once per input row."""

    def __init__(self, working_dir: Path, config: MafPrsConfig):
        self._working_dir = working_dir
        self._config = config
        # Factory only — never cache an instance.  MAF workflows do not
        # support concurrent run() on the same instance.
        self._create_workflow = None
        # User-provided customisation hooks (src/hooks.py).
        self._hooks = None

    # ---- init ---------------------------------------------------------
    def init(self) -> None:
        if str(self._working_dir) not in sys.path:
            sys.path.insert(0, str(self._working_dir))

        # `hooks` is imported *after* sys.path is wired so it can do
        # `from workflow import ...` at module load.
        import hooks  # noqa: E402

        hooks.setup(self._config)
        self._hooks = hooks

        # The MAF workflow project must export a `create_workflow()` factory
        # (per the promptflow-to-maf skill rule).  If your file lives
        # somewhere else, change this import.
        from workflow import create_workflow  # noqa: E402
        self._create_workflow = create_workflow

        self._setup_tracing()

    # ---- per-row ------------------------------------------------------
    async def execute(self, row: dict, row_number: int) -> dict:
        """Run the workflow for one row.  Catches exceptions per-row so a
        single bad row does not poison the whole mini-batch (PF behaviour was
        to fail-and-retry the batch; tune via `error_threshold` /
        `mini_batch_error_threshold` in component.yaml if you want that)."""
        assert self._create_workflow is not None, "init() was not called"
        workflow = self._create_workflow()
        try:
            wf_input = self._hooks.build_workflow_input(row)
            result = await workflow.run(wf_input)
            outputs = result.get_outputs() or [None]
            return {
                "line_number": row_number,
                "input": row,
                "output": self._hooks.serialize_output(outputs[0]),
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 — per-row isolation
            logger.exception("Row %d failed", row_number)
            return {
                "line_number": row_number,
                "input": row,
                "output": None,
                "error": f"{type(exc).__name__}: {exc}",
            }

    # ---- finalize -----------------------------------------------------
    def finalize(self) -> None:
        """Close any cached chat clients / flush OTel here."""
        # No-op by default; the workflow factory builds clients per-row, so
        # there is nothing to close at the executor level.  If your hooks.py
        # caches a shared client, add a `teardown()` hook and call it here.
        return None

    # ---- internal -----------------------------------------------------
    def _setup_tracing(self) -> None:
        """Optional Application Insights tracing.  See the maf-tracing skill."""
        conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        if not conn:
            return
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
            from agent_framework.observability import configure_otel_providers

            configure_azure_monitor(connection_string=conn)
            configure_otel_providers()
            logger.info("Application Insights tracing enabled.")
        except ImportError:
            logger.warning(
                "APPLICATIONINSIGHTS_CONNECTION_STRING is set but "
                "azure-monitor-opentelemetry is not installed; skipping."
            )

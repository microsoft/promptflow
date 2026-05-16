"""
Per-row execution of a MAF workflow.

`workflow_loader.load_workflow()` (from the migration guide root) is used as
the per-row factory. Each call re-imports the workflow file via
`importlib.util`, producing a fresh module-level `workflow` object — required
because MAF workflows do not support concurrent `run()` on the same instance.

All per-workflow customisation lives in `src/hooks.py`; this driver is generic.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from .config import MafPrsConfig

logger = logging.getLogger("maf-prs.executor")


class MafWorkflowExecutor:
    """Drives a MAF workflow once per input row."""

    def __init__(self, working_dir: Path, config: MafPrsConfig):
        self._working_dir = working_dir
        self._config = config
        # Factory only — never cache a workflow instance across rows.
        self._create_workflow: Optional[Callable[[], Any]] = None
        self._hooks: Any = None

    # ---- init ---------------------------------------------------------
    def init(self) -> None:
        # Make the migration guide root (which contains workflow_loader.py and
        # the wrapped workflow file) importable.
        if str(self._working_dir) not in sys.path:
            sys.path.insert(0, str(self._working_dir))

        # `hooks` is imported *after* sys.path is wired so it can perform
        # workflow-relative imports at module load.
        import hooks  # noqa: E402

        hooks.setup(self._config)
        self._hooks = hooks

        # Tell workflow_loader which file to import. Each `load_workflow()`
        # call re-execs the module, giving a fresh `workflow` per row.
        if self._config.maf_workflow_file:
            os.environ["MAF_WORKFLOW_FILE"] = self._config.maf_workflow_file

        from workflow_loader import load_workflow  # noqa: E402

        def _factory() -> Any:
            return load_workflow()

        self._create_workflow = _factory
        self._setup_tracing()

    # ---- per-row ------------------------------------------------------
    async def execute(self, row: dict, row_number: int) -> dict:
        """Run the workflow for one row. Per-row error isolation so a single
        bad row does not poison the mini-batch."""
        assert self._create_workflow is not None, "init() was not called"
        try:
            # Build a fresh workflow per row (re-imports the module so the
            # start executor is re-instantiated). Inside the try/except so
            # construction errors (e.g. missing env vars) are captured as
            # per-row errors rather than failing the whole mini-batch.
            workflow = self._create_workflow()
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
        return None

    # ---- internal -----------------------------------------------------
    def _setup_tracing(self) -> None:
        """Optional Application Insights tracing (Phase 4a)."""
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

"""
Mini-batch orchestration.

Equivalent of promptflow-parallel's `AbstractParallelRunProcessor`:
    PF                                              MAF (this file)
    -----------------------------------------       --------------------------------
    create_processor(working_dir, args)             create_processor(working_dir, args)
    Row.from_dict(data, row_number=base+i)          executor.execute(row, base+i)
    self._executor.execute(row)                     await executor.execute(...)
    json.dumps(result_dict, cls=DataClassEncoder)   json.dumps(result, default=str)
    AggregationFinalizer + _ComponentRunFinalizer   executor.finalize() + loop.close()

The processor:
  * holds the asyncio event loop (created once in init(), reused across all
    run() calls — see references/gotchas.md #2 for why);
  * dispatches rows to the executor with `asyncio.gather` for in-process row
    concurrency (bounded by `max_concurrency_per_instance` in component.yaml);
  * preserves PRS row-order and row-count so the appended JSONL lines match
    the input data.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Iterable, List, Optional

import pandas as pd

from .config import MafPrsConfig, parse_args
from .executor import MafWorkflowExecutor

logger = logging.getLogger("maf-prs.processor")


class MafWorkflowProcessor:
    """PRS processor — drives one MafWorkflowExecutor per worker process."""

    def __init__(self, working_dir: Path, args: Optional[List[str]] = None):
        self._working_dir = working_dir
        self._args = args
        self._cfg: Optional[MafPrsConfig] = None
        self._executor: Optional[MafWorkflowExecutor] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ---- PRS: init ----------------------------------------------------
    def init(self) -> None:
        self._cfg = parse_args(self._args)
        # Re-use a single event loop across all run() invocations.  Calling
        # asyncio.run() per row leaks transports inside many Azure SDK clients.
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._executor = MafWorkflowExecutor(self._working_dir, self._cfg)
        self._executor.init()
        if self._cfg.debug_output_dir:
            self._cfg.debug_output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("MAF PRS processor initialised: cfg=%s", self._cfg)

    # ---- PRS: process(mini_batch, context) ----------------------------
    def process(self, mini_batch: Any, context: Any) -> List[str]:
        """Returns one JSON string per input row.  PRS appends each as a
        line to outputs.flow_outputs (the AML equivalent of PF's
        `parallel_run_step.jsonl`)."""
        assert self._executor is not None and self._loop is not None, "init() was not called"
        base = getattr(context, "global_row_index_lower_bound", 0)
        minibatch_id = getattr(context, "minibatch_index", "?")
        rows = list(self._iter_rows(mini_batch))
        logger.info("mini_batch %s: %d rows (base row_number=%d)", minibatch_id, len(rows), base)

        async def _run_all() -> List[dict]:
            return await asyncio.gather(
                *(self._executor.execute(row, base + i) for i, row in enumerate(rows))
            )

        results = self._loop.run_until_complete(_run_all())
        return [json.dumps(r, default=str) for r in results]

    # ---- PRS: shutdown / finalize ------------------------------------
    def finalize(self) -> None:
        try:
            if self._executor is not None:
                self._executor.finalize()
        finally:
            if self._loop is not None and not self._loop.is_closed():
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
                self._loop.close()

    # ---- helpers ------------------------------------------------------
    @staticmethod
    def _iter_rows(mini_batch: Any) -> Iterable[dict]:
        """Normalise the PRS mini_batch into a stream of row dicts.

        PRS dispatches one of three shapes:
          * `pandas.DataFrame` for tabular inputs.
          * `list[dict]` when input is `uri_file` + `--amlbi_file_format jsonl`
            (PRS parses the jsonl and hands each row as a dict).  See
            gotchas.md #12 for the PF-compat workaround that uses this path.
          * `list[str]` of file paths when input is `uri_folder` of opaque files.
        """
        if isinstance(mini_batch, pd.DataFrame):
            yield from mini_batch.to_dict(orient="records")
            return
        for item in mini_batch:
            if isinstance(item, dict):
                yield item
            else:
                yield {"path": str(item)}


def create_processor(working_dir: Path, args: Optional[List[str]] = None) -> MafWorkflowProcessor:
    return MafWorkflowProcessor(working_dir, args)

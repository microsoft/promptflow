"""
EvalRunner — batch evaluation orchestrator for MAF workflows.

Bridges the gap between MAF's single-invocation workflow model and PromptFlow's
batch-level `aggregation: true` pattern.

Usage:
    runner = EvalRunner(workflow, aggregate_fn, input_mapping={"values": "processed_results"})
    result = await runner.run(dataset)
    print(result.metrics)
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class EvalResult:
    """Result of a batch evaluation run."""

    per_row_outputs: List[Any]
    metrics: Dict[str, Any]
    errors: List[tuple] = field(default_factory=list)


class EvalRunner:
    """Runs a MAF workflow per row, collects outputs, then calls an aggregation function.

    This mirrors PromptFlow's two-phase execution model:
      Phase 1 — run each row through the workflow concurrently
      Phase 2 — pass all collected outputs to the aggregation function

    MAF workflows do not support concurrent execution on a single instance,
    so `workflow_factory` creates a fresh workflow for each concurrent row.

    :param workflow_factory: A zero-arg callable that returns a built MAF workflow.
    :param aggregate_fn: A function that receives collected outputs and returns a metrics dict.
    :param concurrency: Max concurrent workflow.run() calls (prevents rate-limit errors).
    :param input_mapping: Optional rename map for transposed keys → aggregation function params.
        For single-value outputs, _transpose produces {"values": [...]}.  If the aggregation
        function expects a different param name (e.g., "processed_results"), pass
        {"values": "processed_results"}.
    """

    def __init__(
        self,
        workflow_factory: Callable[[], Any],
        aggregate_fn: Callable[..., dict],
        concurrency: int = 5,
        input_mapping: Optional[Dict[str, str]] = None,
    ):
        self._workflow_factory = workflow_factory
        self._aggregate_fn = aggregate_fn
        self._concurrency = concurrency
        self._input_mapping = input_mapping

    async def run(self, dataset: List[Any]) -> EvalResult:
        """Execute the full eval pipeline: per-row → collect → aggregate.

        :param dataset: List of inputs to pass to workflow.run() (one per row).
        :returns: EvalResult with per-row outputs, metrics, and any errors.
        """
        semaphore = asyncio.Semaphore(self._concurrency)
        per_row_outputs: List[Any] = [None] * len(dataset)
        errors: List[tuple] = []

        async def _run_row(index: int, row: Any) -> None:
            async with semaphore:
                wf = self._workflow_factory()
                result = await wf.run(row)
                per_row_outputs[index] = result.get_outputs()[0]

        # Phase 1: run all rows concurrently (bounded by semaphore)
        tasks = [_run_row(i, row) for i, row in enumerate(dataset)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate successes from failures
        succeeded_outputs: List[Any] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                errors.append((i, r))
            else:
                succeeded_outputs.append(per_row_outputs[i])

        # Transpose outputs into aggregation inputs
        aggregation_inputs = self._transpose(succeeded_outputs)

        # Apply parameter name mapping if provided
        if self._input_mapping:
            aggregation_inputs = {
                self._input_mapping.get(k, k): v for k, v in aggregation_inputs.items()
            }

        # Phase 2: call aggregation function
        metrics = self._aggregate_fn(**aggregation_inputs)

        return EvalResult(
            per_row_outputs=succeeded_outputs,
            metrics=metrics,
            errors=errors,
        )

    @staticmethod
    def _transpose(outputs: List[Any]) -> Dict[str, Any]:
        """Transpose per-row outputs into aggregation-ready keyword args.

        - If outputs are plain values (str, int, float): {"values": [v1, v2, ...]}
        - If outputs are dicts: {key: [row1[key], row2[key], ...]} for each key
        """
        if not outputs:
            return {"values": []}
        if not isinstance(outputs[0], dict):
            return {"values": outputs}
        keys = outputs[0].keys()
        return {k: [o[k] for o in outputs] for k in keys}

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
    """Runs a MAF workflow per row, collects outputs, then calls an aggregation function."""

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
        semaphore = asyncio.Semaphore(self._concurrency)
        per_row_outputs: List[Any] = [None] * len(dataset)
        errors: List[tuple] = []

        async def _run_row(index: int, row: Any) -> None:
            async with semaphore:
                wf = self._workflow_factory()
                result = await wf.run(row)
                per_row_outputs[index] = result.get_outputs()[0]

        tasks = [_run_row(i, row) for i, row in enumerate(dataset)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        succeeded_outputs: List[Any] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                errors.append((i, r))
            else:
                succeeded_outputs.append(per_row_outputs[i])

        aggregation_inputs = self._transpose(succeeded_outputs)
        if self._input_mapping:
            aggregation_inputs = {
                self._input_mapping.get(k, k): v for k, v in aggregation_inputs.items()
            }

        metrics = self._aggregate_fn(**aggregation_inputs)
        return EvalResult(
            per_row_outputs=succeeded_outputs,
            metrics=metrics,
            errors=errors,
        )

    @staticmethod
    def _transpose(outputs: List[Any]) -> Dict[str, Any]:
        if not outputs:
            return {"values": []}
        if not isinstance(outputs[0], dict):
            return {"values": outputs}
        keys = outputs[0].keys()
        return {k: [o[k] for o in outputs] for k in keys}

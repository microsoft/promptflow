# Example: Evaluation Flow (Batch with Aggregation)

> Reference example. Read alongside [topics/evaluation-flows.md](../topics/evaluation-flows.md) when converting a flow with `aggregation: true`.

This converts an evaluation flow with a per-row `line_process` node and an `aggregation: true` node.

## Original `flow.dag.yaml`

```yaml
nodes:
- name: line_process
  type: python
  source:
    type: code
    path: line_process.py
  inputs:
    groundtruth: ${inputs.groundtruth}
    prediction: ${inputs.prediction}
- name: aggregate
  type: python
  source:
    type: code
    path: aggregate.py
  inputs:
    processed_results: ${line_process.output}
  aggregation: true
```

## `workflow.py` — Per-row workflow with factory function

```python
import asyncio
from dataclasses import dataclass
from typing_extensions import Never
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler


@dataclass
class EvalInput:
    groundtruth: str
    prediction: str


class LineProcessExecutor(Executor):
    @handler
    async def process(self, input: EvalInput, ctx: WorkflowContext[Never, str]) -> None:
        result = "Correct" if input.groundtruth.lower() == input.prediction.lower() else "Incorrect"
        await ctx.yield_output(result)


def create_workflow():
    """Create a fresh workflow instance.

    MAF workflows do not support concurrent execution, so each batch row
    needs its own workflow instance.
    """
    _line_process = LineProcessExecutor(id="line_process")
    return WorkflowBuilder(name="EvalBasicRow", start_executor=_line_process).build()
```

## `aggregation.py` — Standalone aggregation function

```python
from typing import Dict, List


def aggregate(processed_results: List[str]) -> Dict[str, int]:
    results_num = len(processed_results)
    correct_num = processed_results.count("Correct")
    return {
        "results_num": results_num,
        "correct_num": correct_num,
    }
```

## `eval_runner.py`

Copy [templates/eval_runner.py](../templates/eval_runner.py) verbatim.

## `run_eval.py` — Entry point

```python
import argparse
import asyncio
import json
from pathlib import Path
from aggregation import aggregate
from eval_runner import EvalRunner
from workflow import EvalInput, create_workflow

DEFAULT_DATA = Path(__file__).parent / "data.jsonl"


def load_dataset(path: Path) -> list[EvalInput]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                obj = json.loads(line)
                rows.append(EvalInput(groundtruth=obj["groundtruth"], prediction=obj["prediction"]))
    return rows


async def main(data_path: Path, concurrency: int):
    dataset = load_dataset(data_path)
    print(f"Loaded {len(dataset)} rows from {data_path}")

    runner = EvalRunner(
        workflow_factory=create_workflow,
        aggregate_fn=aggregate,
        concurrency=concurrency,
        input_mapping={"values": "processed_results"},
    )
    result = await runner.run(dataset)

    print(f"\n--- Metrics ---")
    for key, value in result.metrics.items():
        print(f"  {key}: {value}")
    if result.errors:
        print(f"\n--- Errors ({len(result.errors)}) ---")
        for idx, err in result.errors:
            print(f"  Row {idx}: {err}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(main(args.data, args.concurrency))
```

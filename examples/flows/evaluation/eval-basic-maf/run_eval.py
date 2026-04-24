"""
Entry point: run the eval-basic evaluation as a batch.

Loads the test dataset, runs the per-row workflow for each row,
then aggregates results.

Usage:
    python run_eval.py
    python run_eval.py --data path/to/data.jsonl --concurrency 10
"""

import argparse
import asyncio
import json
from pathlib import Path

from aggregation import aggregate
from eval_runner import EvalResult, EvalRunner
from workflow import EvalInput, create_workflow

DEFAULT_DATA = Path(__file__).parent / "data.jsonl"


def load_dataset(path: Path) -> list[EvalInput]:
    """Load a JSONL file into a list of EvalInput."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                obj = json.loads(line)
                rows.append(EvalInput(groundtruth=obj["groundtruth"], prediction=obj["prediction"]))
    return rows


async def main(data_path: Path, concurrency: int) -> EvalResult:
    dataset = load_dataset(data_path)
    print(f"Loaded {len(dataset)} rows from {data_path}")

    runner = EvalRunner(
        workflow_factory=create_workflow,
        aggregate_fn=aggregate,
        concurrency=concurrency,
        input_mapping={"values": "processed_results"},
    )

    result = await runner.run(dataset)

    print("\n--- Per-row outputs ---")
    for i, output in enumerate(result.per_row_outputs):
        print(f"  Row {i}: {output}")

    print("\n--- Metrics ---")
    for key, value in result.metrics.items():
        print(f"  {key}: {value}")

    if result.errors:
        print(f"\n--- Errors ({len(result.errors)}) ---")
        for idx, err in result.errors:
            print(f"  Row {idx}: {err}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run eval-basic evaluation batch")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Path to JSONL dataset")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent workflow runs")
    args = parser.parse_args()
    asyncio.run(main(args.data, args.concurrency))

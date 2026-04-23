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
                rows.append(EvalInput(document=obj["document"], summary=obj["summary"]))
    return rows


async def main(data_path: Path, concurrency: int):
    dataset = load_dataset(data_path)
    print(f"Loaded {len(dataset)} rows from {data_path}")

    runner = EvalRunner(
        workflow_factory=create_workflow,
        aggregate_fn=aggregate,
        concurrency=concurrency,
    )
    result = await runner.run(dataset)

    print(f"\n--- Metrics ---")
    for key, value in result.metrics.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(main(args.data, args.concurrency))

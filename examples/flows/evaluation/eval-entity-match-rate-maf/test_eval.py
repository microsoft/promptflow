import asyncio
import json
from pathlib import Path
from aggregation import aggregate
from eval_runner import EvalRunner
from workflow import EvalInput, create_workflow


async def test_exact_match():
    wf = create_workflow()
    result = await wf.run(EvalInput(
        entities=["software engineer", "CEO"],
        ground_truth='"CEO, Software Engineer, Finance Manager"'
    ))
    output = result.get_outputs()[0]
    assert output["exact_match"] == 0
    assert output["partial_match"] == 1
    print("PASS: test_exact_match")


async def test_batch():
    dataset = [
        EvalInput(entities=["CEO"], ground_truth="CEO, Engineer"),
        EvalInput(entities=["CEO", "Engineer"], ground_truth="CEO, Engineer"),
    ]
    runner = EvalRunner(
        workflow_factory=create_workflow,
        aggregate_fn=aggregate,
        concurrency=5,
    )
    result = await runner.run(dataset)
    assert result.metrics["partial_match_rate"] == 1.0
    print("PASS: test_batch")


async def test_data_jsonl():
    """Run eval on every row in data.jsonl"""
    data_path = Path(__file__).parent / "data.jsonl"
    rows = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    wf = create_workflow()
    for i, row in enumerate(rows):
        result = await wf.run(EvalInput(
            entities=row["entities"],
            ground_truth=row["ground_truth"],
        ))
        output = result.get_outputs()[0]
        assert isinstance(output, dict), f"Row {i}: expected dict, got {type(output)}"
        print(f"  Row {i}: output={output}")
    print(f"PASS: test_data_jsonl ({len(rows)} rows)")


async def main():
    await test_exact_match()
    await test_batch()
    await test_data_jsonl()
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

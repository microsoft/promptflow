import asyncio
import json
from pathlib import Path
from aggregation import aggregate
from eval_runner import EvalRunner
from workflow import EvalInput, create_workflow


async def test_correct():
    wf = create_workflow()
    result = await wf.run(EvalInput(groundtruth="APP", prediction="APP"))
    assert result.get_outputs()[0] == "Correct"
    print("PASS: test_correct")


async def test_incorrect():
    wf = create_workflow()
    result = await wf.run(EvalInput(groundtruth="APP", prediction="WEB"))
    assert result.get_outputs()[0] == "Incorrect"
    print("PASS: test_incorrect")


async def test_batch():
    dataset = [
        EvalInput(groundtruth="APP", prediction="APP"),
        EvalInput(groundtruth="Channel", prediction="Channel"),
        EvalInput(groundtruth="Academic", prediction="Finance"),
    ]
    runner = EvalRunner(
        workflow_factory=create_workflow,
        aggregate_fn=aggregate,
        concurrency=5,
        input_mapping={"values": "grades"},
    )
    result = await runner.run(dataset)
    assert result.metrics["accuracy"] == 0.67
    print("PASS: test_batch")


async def test_data_jsonl():
    """Run eval on every row in data.jsonl"""
    data_path = Path(__file__).parent / "data.jsonl"
    rows = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    wf = create_workflow()
    for i, row in enumerate(rows):
        result = await wf.run(EvalInput(
            groundtruth=row["groundtruth"],
            prediction=row["prediction"],
        ))
        grade = result.get_outputs()[0]
        assert grade in ("Correct", "Incorrect"), f"Row {i}: unexpected grade '{grade}'"
        print(f"  Row {i}: grade={grade}")
    print(f"PASS: test_data_jsonl ({len(rows)} rows)")


async def main():
    await test_correct()
    await test_incorrect()
    await test_batch()
    await test_data_jsonl()
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

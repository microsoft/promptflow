import asyncio
import json
from pathlib import Path
from aggregation import aggregate
from eval_runner import EvalRunner
from workflow import EvalInput, create_workflow


async def test_fraction_match():
    wf = create_workflow()
    result = await wf.run(EvalInput(groundtruth="3/5", prediction="6/10"))
    assert result.get_outputs()[0] == 1
    print("PASS: test_fraction_match")


async def test_float_fraction():
    wf = create_workflow()
    result = await wf.run(EvalInput(groundtruth="1/2", prediction="0.5"))
    assert result.get_outputs()[0] == 1
    print("PASS: test_float_fraction")


async def test_mismatch():
    wf = create_workflow()
    result = await wf.run(EvalInput(groundtruth="3", prediction="5"))
    assert result.get_outputs()[0] == -1
    print("PASS: test_mismatch")


async def test_batch():
    dataset = [
        EvalInput(groundtruth="3/5", prediction="6/10"),
        EvalInput(groundtruth="1/2", prediction="0.5"),
        EvalInput(groundtruth="3", prediction="5"),
    ]
    runner = EvalRunner(
        workflow_factory=create_workflow,
        aggregate_fn=aggregate,
        concurrency=5,
        input_mapping={"values": "processed_results"},
    )
    result = await runner.run(dataset)
    assert result.metrics["num_correct"] == 2
    assert result.metrics["num_exception"] == 1
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
        score = result.get_outputs()[0]
        assert isinstance(score, int), f"Row {i}: expected int, got {type(score)}"
        print(f"  Row {i}: score={score}")
    print(f"PASS: test_data_jsonl ({len(rows)} rows)")


async def main():
    await test_fraction_match()
    await test_float_fraction()
    await test_mismatch()
    await test_batch()
    await test_data_jsonl()
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
from pathlib import Path
from aggregation import aggregate
from eval_runner import EvalRunner
from workflow import EvalInput, create_workflow


async def test_single_correct():
    wf = create_workflow()
    result = await wf.run(EvalInput(groundtruth="1.0", prediction="1"))
    assert result.get_outputs()[0] == 1
    print("PASS: test_single_correct")


async def test_single_incorrect():
    wf = create_workflow()
    result = await wf.run(EvalInput(groundtruth="2.1", prediction="2.0"))
    assert result.get_outputs()[0] == 0
    print("PASS: test_single_incorrect")


async def test_json_error():
    wf = create_workflow()
    result = await wf.run(EvalInput(groundtruth="1.0", prediction="JSONDecodeError"))
    assert result.get_outputs()[0] == -1
    print("PASS: test_json_error")


async def test_batch():
    dataset = [
        EvalInput(groundtruth="1.0", prediction="1"),
        EvalInput(groundtruth="3.14", prediction="3.1415926"),
        EvalInput(groundtruth="1.0", prediction="JSONDecodeError"),
    ]
    runner = EvalRunner(
        workflow_factory=create_workflow,
        aggregate_fn=aggregate,
        concurrency=5,
        input_mapping={"values": "processed_results"},
    )
    result = await runner.run(dataset)
    assert result.metrics["num_total"] == 3
    assert result.metrics["num_correct"] == 2
    assert result.metrics["num_exception"] == 1
    print("PASS: test_batch")


async def test_data_jsonl():
    """Run eval on every row in test_data.jsonl"""
    data_path = Path(__file__).parent / "test_data.jsonl"
    rows = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    wf = create_workflow()
    for i, row in enumerate(rows):
        result = await wf.run(EvalInput(
            groundtruth=row["groundtruth"],
            prediction=row["answer"],
        ))
        score = result.get_outputs()[0]
        assert isinstance(score, int), f"Row {i}: expected int, got {type(score)}"
        print(f"  Row {i}: score={score}")
    print(f"PASS: test_data_jsonl ({len(rows)} rows)")


async def main():
    await test_single_correct()
    await test_single_incorrect()
    await test_json_error()
    await test_batch()
    await test_data_jsonl()
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

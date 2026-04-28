"""
Test script for the eval-basic MAF conversion.

Verifies both the per-row workflow and the full batch evaluation pipeline.
"""

import asyncio
import json
from pathlib import Path

from aggregation import aggregate
from eval_runner import EvalRunner
from workflow import EvalInput, create_workflow


async def test_single_row():
    """Test the per-row workflow with a matching pair."""
    wf = create_workflow()
    result = await wf.run(EvalInput(groundtruth="sunny", prediction="Sunny"))
    output = result.get_outputs()[0]
    assert output == "Correct", f"Expected 'Correct', got '{output}'"
    print("PASS: test_single_row")


async def test_single_row_mismatch():
    """Test the per-row workflow with a non-matching pair."""
    wf = create_workflow()
    result = await wf.run(EvalInput(groundtruth="sunny", prediction="rainy"))
    output = result.get_outputs()[0]
    assert output == "Incorrect", f"Expected 'Incorrect', got '{output}'"
    print("PASS: test_single_row_mismatch")


async def test_batch_evaluation():
    """Test the full batch pipeline with EvalRunner."""
    dataset = [
        EvalInput(groundtruth="APP", prediction="APP"),
        EvalInput(groundtruth="APP", prediction="WEB"),
        EvalInput(groundtruth="DB", prediction="db"),
    ]

    runner = EvalRunner(
        workflow_factory=create_workflow,
        aggregate_fn=aggregate,
        concurrency=5,
        input_mapping={"values": "processed_results"},
    )
    result = await runner.run(dataset)

    assert result.per_row_outputs == ["Correct", "Incorrect", "Correct"], (
        f"Unexpected per-row outputs: {result.per_row_outputs}"
    )
    assert result.metrics["results_num"] == 3, f"Expected 3 results, got {result.metrics['results_num']}"
    assert result.metrics["correct_num"] == 2, f"Expected 2 correct, got {result.metrics['correct_num']}"
    assert len(result.errors) == 0, f"Unexpected errors: {result.errors}"
    print("PASS: test_batch_evaluation")


async def test_empty_dataset():
    """Test with an empty dataset."""
    runner = EvalRunner(
        workflow_factory=create_workflow,
        aggregate_fn=aggregate,
        concurrency=5,
        input_mapping={"values": "processed_results"},
    )
    result = await runner.run([])
    assert result.per_row_outputs == []
    assert result.metrics["results_num"] == 0
    assert len(result.errors) == 0
    print("PASS: test_empty_dataset")


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
    await test_single_row()
    await test_single_row_mismatch()
    await test_batch_evaluation()
    await test_empty_dataset()
    await test_data_jsonl()
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

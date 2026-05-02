import asyncio
import json
from pathlib import Path
from workflow import EvalInput, create_workflow


async def test_single_row():
    """Smoke test - requires Azure OpenAI credentials in .env"""
    wf = create_workflow()
    result = await wf.run(EvalInput(
        question="Which tent is the most waterproof?",
        answer="The Alpine Explorer Tent is the most waterproof.",
        context="From the our product list, the alpine explorer tent is the most waterproof.",
        ground_truth="The Alpine Explorer Tent has the highest rainfly waterproof rating at 3000m",
    ))
    scores = result.get_outputs()[0]
    assert isinstance(scores, dict)
    assert len(scores) == 8
    print(f"PASS: test_single_row (scores={scores})")


async def test_selective_metrics():
    """Test with only some metrics enabled"""
    wf = create_workflow()
    result = await wf.run(EvalInput(
        question="What is AI?",
        answer="Artificial intelligence.",
        context="AI stands for artificial intelligence.",
        ground_truth="Artificial intelligence",
        metrics="grounding,creativity",
    ))
    scores = result.get_outputs()[0]
    assert scores["answer_correctness"] is None
    assert scores["context_recall"] is None
    print(f"PASS: test_selective_metrics (scores={scores})")


async def test_data_jsonl():
    """Run eval on every row in data.jsonl"""
    data_path = Path(__file__).parent / "data.jsonl"
    rows = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    wf = create_workflow()
    for i, row in enumerate(rows):
        context = row.get("context", "")
        if isinstance(context, list):
            context = "\n".join(context)
        result = await wf.run(EvalInput(
            question=row["question"],
            answer=row["answer"],
            context=context,
            ground_truth=row["ground_truth"],
        ))
        scores = result.get_outputs()[0]
        assert isinstance(scores, dict), f"Row {i}: expected dict, got {type(scores)}"
        print(f"  Row {i}: scores={scores}")
    print(f"PASS: test_data_jsonl ({len(rows)} rows)")


async def main():
    await test_single_row()
    await test_selective_metrics()
    await test_data_jsonl()
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

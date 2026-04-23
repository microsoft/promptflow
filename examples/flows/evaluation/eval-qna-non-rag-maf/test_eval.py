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
    assert "f1_score" in scores
    assert "gpt_coherence" in scores
    assert "ada_similarity" in scores
    print(f"PASS: test_single_row (scores={scores})")


async def test_f1_only():
    """Test f1 metric without LLM"""
    wf = create_workflow()
    result = await wf.run(EvalInput(
        question="What?",
        answer="The Alpine Explorer Tent",
        context="",
        ground_truth="The Alpine Explorer Tent is waterproof",
        metrics="f1_score",
    ))
    scores = result.get_outputs()[0]
    assert scores["f1_score"] > 0
    print(f"PASS: test_f1_only (f1={scores['f1_score']})")


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
    await test_f1_only()
    await test_data_jsonl()
    print("\nAll tests passed! (run test_single_row with Azure OpenAI credentials)")


if __name__ == "__main__":
    asyncio.run(main())

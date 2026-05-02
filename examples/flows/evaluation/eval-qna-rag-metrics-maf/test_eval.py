import asyncio
import json
from pathlib import Path
from workflow import EvalInput, create_workflow


async def test_single_row():
    """Smoke test - requires Azure OpenAI credentials in .env"""
    wf = create_workflow()
    result = await wf.run(EvalInput(
        question="Which tent is the most waterproof?",
        answer="The Alpine Explorer Tent has the highest waterproof rating at 3000mm.",
        documents='{"documents": [{"content": "Alpine Explorer Tent has 3000mm waterproof rating."}]}',
    ))
    scores = result.get_outputs()[0]
    assert isinstance(scores, dict)
    assert "gpt_groundedness" in scores
    assert "gpt_relevance" in scores
    assert "gpt_retrieval_score" in scores
    print(f"PASS: test_single_row (scores={scores})")


async def test_data_jsonl():
    """Run eval on every row in data.jsonl"""
    data_path = Path(__file__).parent / "data.jsonl"
    rows = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    wf = create_workflow()
    for i, row in enumerate(rows):
        result = await wf.run(EvalInput(
            question=row["question"],
            answer=row["answer"],
            documents=row["documents"] if isinstance(row["documents"], str) else json.dumps(row["documents"]),
        ))
        scores = result.get_outputs()[0]
        assert isinstance(scores, dict), f"Row {i}: expected dict, got {type(scores)}"
        print(f"  Row {i}: scores={scores}")
    print(f"PASS: test_data_jsonl ({len(rows)} rows)")


async def main():
    await test_single_row()
    await test_data_jsonl()
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import json
from pathlib import Path
from workflow import EvalInput, create_workflow


async def test_single_row():
    """Smoke test - requires Azure OpenAI credentials in .env"""
    wf = create_workflow()
    result = await wf.run(EvalInput(
        question="What is BERT?",
        answer="BERT is a language model.",
        context="BERT is a pre-trained language representation model.",
    ))
    score = result.get_outputs()[0]
    assert isinstance(score, float)
    print(f"PASS: test_single_row (score={score})")


async def test_data_jsonl():
    """Run eval on every row in data.jsonl"""
    data_path = Path(__file__).parent / "data.jsonl"
    rows = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    wf = create_workflow()
    for i, row in enumerate(rows):
        context = row["context"]
        if isinstance(context, list):
            context = "\n".join(context)
        result = await wf.run(EvalInput(
            question=row["question"],
            answer=row["answer"],
            context=context,
        ))
        score = result.get_outputs()[0]
        assert isinstance(score, float), f"Row {i}: expected float, got {type(score)}"
        print(f"  Row {i}: score={score}")
    print(f"PASS: test_data_jsonl ({len(rows)} rows)")


async def main():
    await test_single_row()
    await test_data_jsonl()
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())

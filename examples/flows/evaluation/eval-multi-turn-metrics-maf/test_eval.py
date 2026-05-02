import asyncio
import json
from pathlib import Path
from workflow import EvalInput, create_workflow


async def test_single_row():
    """Smoke test - requires Azure OpenAI credentials in .env"""
    chat_history = [
        {
            "inputs": {"question": "What is prompt flow?", "ground_truth": "A tool for LLM apps."},
            "outputs": {
                "answer": "Prompt flow is a tool to build LLM applications.",
                "context": "Prompt flow is an open-source tool for building LLM applications.",
            },
        },
    ]
    wf = create_workflow()
    result = await wf.run(EvalInput(chat_history=chat_history))
    scores = result.get_outputs()[0]
    assert isinstance(scores, dict)
    assert "answer_relevance" in scores
    assert "grounding" in scores
    print(f"PASS: test_single_row (scores={scores})")


async def test_selective_metrics():
    """Test with only some metrics enabled"""
    chat_history = [
        {
            "inputs": {"question": "Hello", "ground_truth": "Hi"},
            "outputs": {"answer": "Hi there!", "context": "Greeting context."},
        },
    ]
    wf = create_workflow()
    result = await wf.run(EvalInput(chat_history=chat_history, metrics="creativity,answer_relevance"))
    scores = result.get_outputs()[0]
    assert scores["grounding"] is None
    assert scores["conversation_quality"] is None
    print(f"PASS: test_selective_metrics (scores={scores})")


async def test_data_jsonl():
    """Run eval on every row in data.jsonl"""
    data_path = Path(__file__).parent / "data.jsonl"
    rows = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    wf = create_workflow()
    for i, row in enumerate(rows):
        result = await wf.run(EvalInput(
            chat_history=row["chat_history"],
            metrics=row.get("metrics", "creativity,conversation_quality,answer_relevance,grounding"),
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

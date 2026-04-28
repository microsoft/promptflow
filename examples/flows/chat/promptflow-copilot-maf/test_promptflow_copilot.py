"""Test script for the promptflow-copilot MAF workflow."""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from workflow import ChatInput, create_workflow  # noqa: E402


async def test_relevant_question():
    print("--- relevant question ---")
    workflow = create_workflow()
    result = await workflow.run(ChatInput(question="How do I deploy a flow?"))
    print("Answer:", result.get_outputs()[0])


async def test_irrelevant_question():
    print("\n--- irrelevant question ---")
    workflow = create_workflow()
    result = await workflow.run(ChatInput(question="What is the weather today?"))
    print("Answer:", result.get_outputs()[0])


async def test_multi_turn():
    print("\n--- multi turn ---")
    history = [
        {
            "inputs": {"question": "What is promptflow?"},
            "outputs": {
                "output": "Prompt flow is a suite of dev tools for LLM apps."
            },
        },
    ]
    workflow = create_workflow()
    result = await workflow.run(ChatInput(question="How do I create a flow?", chat_history=history))
    print("Answer:", result.get_outputs()[0])


async def main():
    await test_relevant_question()
    await test_irrelevant_question()
    await test_multi_turn()


if __name__ == "__main__":
    asyncio.run(main())

"""Test script for the chat-math-variant MAF workflow."""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from workflow import ChatInput, build_workflow  # noqa: E402


async def test_single_turn():
    """Single-turn: ask a simple math question with each variant."""
    for variant in ("variant_0", "variant_1", "variant_2"):
        print(f"\n--- {variant} ---")
        workflow = build_workflow(variant)
        result = await workflow.run(ChatInput(question="1+1=?", variant=variant))
        print("Answer:", result.get_outputs()[0])


async def test_multi_turn():
    """Multi-turn: simulate a conversation, then ask for the sum of all previous answers."""
    workflow = build_workflow("variant_0")

    chat_history = [
        {"inputs": {"question": "1+1=?"}, "outputs": {"answer": "2"}},
        {"inputs": {"question": "2+2=?"}, "outputs": {"answer": "4"}},
        {"inputs": {"question": "3+3=?"}, "outputs": {"answer": "6"}},
    ]

    result = await workflow.run(
        ChatInput(
            question="What is the sum of all the answers you gave so far?",
            chat_history=chat_history,
            variant="variant_0",
        )
    )
    print("\n--- multi-turn (variant_0) ---")
    print("Answer:", result.get_outputs()[0])


async def main():
    await test_single_turn()
    await test_multi_turn()


if __name__ == "__main__":
    asyncio.run(main())

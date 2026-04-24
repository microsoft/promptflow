"""Test script for the chat-with-image MAF workflow."""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from workflow import ChatInput, workflow


async def test_single_turn():
    """Single-turn: ask about an image."""
    result = await workflow.run(
        ChatInput(
            question=[
                "How many colors can you see?",
                {"data:image/png;url": "https://uhf.microsoft.com/images/microsoft/RE1Mu3b.png"},
            ]
        )
    )
    output = result.get_outputs()[0]
    print("Answer:", output)
    assert isinstance(output, str) and len(output) > 0


async def test_multi_turn():
    """Multi-turn: follow-up about the same image."""
    chat_history = [
        {
            "inputs": {
                "question": [{"data:image/png;url": "https://uhf.microsoft.com/images/microsoft/RE1Mu3b.png"}, "What is in this image?"]
            },
            "outputs": {"answer": "This is a logo."},
        }
    ]
    result = await workflow.run(
        ChatInput(
            question=["Describe it in more detail."],
            chat_history=chat_history,
        )
    )
    output = result.get_outputs()[0]
    print("Answer:", output)
    assert isinstance(output, str) and len(output) > 0


async def main():
    await test_single_turn()
    await test_multi_turn()


if __name__ == "__main__":
    asyncio.run(main())

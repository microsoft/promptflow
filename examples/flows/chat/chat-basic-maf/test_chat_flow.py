"""
Sample script to test the Basic Chat MAF workflow.

Run:
    python test_chat_flow.py
"""

import asyncio

from chat_flow import ChatInput, workflow


async def main():
    # Test 1: Single-turn — no chat history
    print("=" * 60)
    print("Test 1: Single-turn (no history)")
    print("=" * 60)
    result = await workflow.run(ChatInput(question="What is ChatGPT?"))
    print(f"Q: What is ChatGPT?")
    print(f"A: {result.get_outputs()[0]}\n")

    # Test 2: Multi-turn — with one prior exchange
    print("=" * 60)
    print("Test 2: Multi-turn (with history)")
    print("=" * 60)
    history = [
        {
            "inputs": {"question": "What is ChatGPT?"},
            "outputs": {"answer": "ChatGPT is a large language model chatbot developed by OpenAI."},
        }
    ]
    result = await workflow.run(
        ChatInput(
            question="How is it different from GPT-4?",
            chat_history=history,
        )
    )
    print(f"Q: How is it different from GPT-4?")
    print(f"A: {result.get_outputs()[0]}\n")

    # Test 3: Multi-turn — longer conversation
    print("=" * 60)
    print("Test 3: Multi-turn (longer conversation)")
    print("=" * 60)
    history = [
        {
            "inputs": {"question": "What is 2+2?"},
            "outputs": {"answer": "4"},
        },
        {
            "inputs": {"question": "Multiply that by 3"},
            "outputs": {"answer": "12"},
        },
    ]
    result = await workflow.run(
        ChatInput(
            question="Now divide by 6",
            chat_history=history,
        )
    )
    print(f"Q: Now divide by 6")
    print(f"A: {result.get_outputs()[0]}\n")


if __name__ == "__main__":
    asyncio.run(main())



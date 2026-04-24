"""Test script for the chat-with-wikipedia MAF workflow."""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from workflow import ChatInput, workflow  # noqa: E402


async def test_single_turn():
    print("--- single turn ---")
    result = await workflow.run(ChatInput(question="What is ChatGPT?"))
    print("Answer:", result.get_outputs()[0])


async def test_multi_turn():
    print("\n--- multi turn ---")
    history = [
        {"inputs": {"question": "What is ChatGPT?"}, "outputs": {"answer": "ChatGPT is an AI chatbot by OpenAI."}},
    ]
    result = await workflow.run(ChatInput(question="Who created it?", chat_history=history))
    print("Answer:", result.get_outputs()[0])


async def main():
    await test_single_turn()
    await test_multi_turn()


if __name__ == "__main__":
    asyncio.run(main())

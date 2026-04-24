"""Test script for the chat-with-pdf MAF workflow."""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from workflow import PdfChatInput, workflow  # noqa: E402


async def test_single_turn():
    print("--- single turn ---")
    result = await workflow.run(
        PdfChatInput(
            question="What is BERT?",
            pdf_url="https://arxiv.org/pdf/1810.04805.pdf",
        )
    )
    output = result.get_outputs()[0]
    print(f"Answer: {output['answer']}")
    print(f"Context: {output['context']}")


async def test_multi_turn():
    print("\n--- multi turn ---")
    history = [
        {
            "inputs": {"question": "What is BERT?"},
            "outputs": {"answer": "BERT is a language model by Google."},
        }
    ]
    result = await workflow.run(
        PdfChatInput(
            question="How was it trained?",
            pdf_url="https://arxiv.org/pdf/1810.04805.pdf",
            chat_history=history,
        )
    )
    output = result.get_outputs()[0]
    print(f"Answer: {output['answer']}")
    print(f"Context: {output['context']}")


async def main():
    await test_single_turn()
    await test_multi_turn()


if __name__ == "__main__":
    asyncio.run(main())

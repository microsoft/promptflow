import asyncio

from workflow_multi_node import ChatInput, workflow


async def main():
    # Single-turn test
    result = await workflow.run(
        ChatInput(
            question="what NLP tasks does it perform well?",
            pdf_url="https://arxiv.org/pdf/1810.04805.pdf",
        )
    )
    output = result.get_outputs()[0]
    print(f"Answer: {output['answer']}")
    print(f"Context: {output['context']}")

    # Multi-turn test
    result2 = await workflow.run(
        ChatInput(
            question="Can you elaborate on the fine-tuning approach?",
            pdf_url="https://arxiv.org/pdf/1810.04805.pdf",
            chat_history=[
                {
                    "inputs": {"question": "what NLP tasks does it perform well?"},
                    "outputs": {"answer": output["answer"]},
                }
            ],
        )
    )
    output2 = result2.get_outputs()[0]
    print(f"\nFollow-up Answer: {output2['answer']}")


if __name__ == "__main__":
    asyncio.run(main())

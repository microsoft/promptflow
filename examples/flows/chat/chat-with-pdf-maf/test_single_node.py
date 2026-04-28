import asyncio

from workflow_single_node import ChatInput, create_workflow


async def main():
    # Single-turn test
    workflow = create_workflow()
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
    workflow2 = create_workflow()
    result2 = await workflow2.run(
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

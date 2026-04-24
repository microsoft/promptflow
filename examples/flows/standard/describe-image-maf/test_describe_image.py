import asyncio

from workflow import ImageInput, workflow


async def main():
    test_cases = [
        {
            "question": "How many colors are there in the image?",
            "input_image": {"data:image/png;url": "https://developer.microsoft.com/_devcom/images/logo-ms-social.png"},
        },
        {
            "question": "What's this image about?",
            "input_image": {"data:image/png;url": "https://developer.microsoft.com/_devcom/images/404.png"},
        },
    ]
    for tc in test_cases:
        print(f"\n--- Question: {tc['question']} ---")
        result = await workflow.run(ImageInput(question=tc["question"], input_image=tc["input_image"]))
        output = result.get_outputs()[0]
        print(f"Answer: {output['answer']}")


if __name__ == "__main__":
    asyncio.run(main())

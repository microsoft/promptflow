import asyncio

from workflow import workflow


async def main():
    result = await workflow.run(
        "If a rectangle has a length of 10 and width of 5, what is the area?"
    )
    output = result.get_outputs()[0]
    print(f"Code: {output.code}")
    print(f"Answer: {output.answer}")


if __name__ == "__main__":
    asyncio.run(main())

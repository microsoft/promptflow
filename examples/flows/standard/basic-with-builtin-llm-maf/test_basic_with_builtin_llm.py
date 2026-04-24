import asyncio

from workflow import workflow


async def main():
    result = await workflow.run("Python Hello World!")
    output = result.get_outputs()[0]
    print(f"Output: {output}")


if __name__ == "__main__":
    asyncio.run(main())

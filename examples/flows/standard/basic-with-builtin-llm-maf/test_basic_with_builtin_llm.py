import asyncio

from workflow import create_workflow


async def main():
    workflow = create_workflow()
    result = await workflow.run("Python Hello World!")
    output = result.get_outputs()[0]
    print(f"Output: {output}")


if __name__ == "__main__":
    asyncio.run(main())

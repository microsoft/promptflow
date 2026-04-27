import asyncio

from workflow import create_workflow


async def main():
    url = "https://arxiv.org/abs/2307.04767"
    print(f"--- Classifying: {url} ---")
    workflow = create_workflow()
    result = await workflow.run(url)
    output = result.get_outputs()[0]
    print(f"Category: {output.get('category')}")
    print(f"Evidence: {output.get('evidence')}")


if __name__ == "__main__":
    asyncio.run(main())

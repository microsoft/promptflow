import asyncio

from workflow import NERInput, workflow


async def main():
    result = await workflow.run(
        NERInput(
            text="Maxime is a data scientist at Auto Dataset and he lives in Paris, France.",
            entity_type="job title",
        )
    )
    print(f"Entities: {result.get_outputs()[0]}")


if __name__ == "__main__":
    asyncio.run(main())

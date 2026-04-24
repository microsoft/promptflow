import asyncio

from workflow import IntentInput, workflow


async def main():
    result = await workflow.run(
        IntentInput(
            history="Customer: I want to return my order\nAgent: Sure, I can help with that.",
            customer_info="Name: John Doe\nOrder: #12345 - Widget A",
        )
    )
    print(f"Intent: {result.get_outputs()[0]}")


if __name__ == "__main__":
    asyncio.run(main())

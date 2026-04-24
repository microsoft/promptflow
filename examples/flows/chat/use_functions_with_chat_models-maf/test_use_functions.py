"""Test script for the use_functions_with_chat_models MAF workflow."""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from workflow import ChatInput, workflow  # noqa: E402


async def test_weather_query():
    print("--- weather query ---")
    result = await workflow.run(
        ChatInput(question="What is the weather like in Boston?")
    )
    print("Answer:", result.get_outputs()[0])


async def test_forecast_query():
    print("\n--- forecast follow-up ---")
    result = await workflow.run(
        ChatInput(
            question="How about London next week?",
            chat_history=[
                {
                    "inputs": {"question": "What is the weather like in Boston?"},
                    "outputs": {
                        "answer": (
                            '{"forecast":["sunny","windy"],'
                            '"location":"Boston",'
                            '"temperature":"72",'
                            '"unit":"fahrenheit"}'
                        ),
                        "llm_output": {
                            "content": None,
                            "function_call": {
                                "name": "get_current_weather",
                                "arguments": '{"location": "Boston"}',
                            },
                            "role": "assistant",
                        },
                    },
                }
            ],
        )
    )
    print("Answer:", result.get_outputs()[0])


async def main():
    await test_weather_query()
    await test_forecast_query()


if __name__ == "__main__":
    asyncio.run(main())

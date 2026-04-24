import asyncio
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

# ---------------------------------------------------------------------------
# Tool functions (from run_function.py)
# ---------------------------------------------------------------------------


def get_current_weather(location: str, unit: str = "fahrenheit") -> dict:
    """Get the current weather in a given location."""
    return {
        "location": location,
        "temperature": "72",
        "unit": unit,
        "forecast": ["sunny", "windy"],
    }


def get_n_day_weather_forecast(location: str, format: str, num_days: int) -> dict:
    """Get next num_days weather in a given location."""
    return {
        "location": location,
        "temperature": "60",
        "format": format,
        "forecast": ["rainy"],
        "num_days": num_days,
    }


INSTRUCTIONS = """\
Don't make assumptions about what values to plug into functions. \
Ask for clarification if a user request is ambiguous."""

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ChatInput:
    question: str
    chat_history: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


class InputExecutor(Executor):
    """Formats chat history (including prior function calls) into a prompt."""

    @handler
    async def receive(self, chat_input: ChatInput, ctx: WorkflowContext[str]) -> None:
        parts: list[str] = []
        for turn in chat_input.chat_history:
            parts.append(f"User: {turn['inputs']['question']}")
            llm_output = turn["outputs"].get("llm_output", {})
            if isinstance(llm_output, dict) and "function_call" in llm_output:
                fc = llm_output["function_call"]
                parts.append(
                    f"Assistant: Function call requested — {fc['name']}({fc['arguments']})"
                )
                parts.append(f"Function result: {turn['outputs']['answer']}")
            else:
                parts.append(f"Assistant: {turn['outputs'].get('answer', '')}")
        parts.append(chat_input.question)
        await ctx.send_message("\n".join(parts))


class FunctionCallingExecutor(Executor):
    """LLM node with tool-use: calls GPT with function definitions,
    then executes the returned function locally."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-35-turbo"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="FunctionCallingAgent",
            instructions=INSTRUCTIONS,
            tools=[get_current_weather, get_n_day_weather_forecast],
        )

    @handler
    async def call_with_tools(self, prompt: str, ctx: WorkflowContext[Never, str]) -> None:
        response = await self._agent.run(prompt)
        await ctx.yield_output(response.text)


# ---------------------------------------------------------------------------
# Workflow: input → function_calling → output
# ---------------------------------------------------------------------------

_input = InputExecutor(id="input")
_function_calling = FunctionCallingExecutor(id="function_calling")

workflow = (
    WorkflowBuilder(name="UseFunctionsWorkflow", start_executor=_input)
    .add_edge(_input, _function_calling)
    .build()
)


async def main():
    # First turn: ask about weather
    result = await workflow.run(
        ChatInput(question="What is the weather like in Boston?")
    )
    print("Answer:", result.get_outputs()[0])

    # Follow-up with chat history
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


if __name__ == "__main__":
    asyncio.run(main())

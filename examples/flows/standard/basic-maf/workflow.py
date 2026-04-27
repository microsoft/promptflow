import asyncio
import os

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

_PROMPT_TEMPLATE = "Write a simple {text} program that displays the greeting message."


class PromptExecutor(Executor):
    @handler
    async def receive(self, text: str, ctx: WorkflowContext[str]) -> None:
        prompt = _PROMPT_TEMPLATE.format(text=text)
        await ctx.send_message(prompt)


class LLMExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="BasicAgent",
            instructions="You are a helpful assistant.",
        )

    @handler
    async def call_llm(self, prompt: str, ctx: WorkflowContext[Never, str]) -> None:
        response = await self._agent.run(prompt)
        await ctx.yield_output(response.text)


def create_workflow():
    """Create a fresh workflow instance.

    MAF workflows do not support concurrent execution, so each
    concurrent caller needs its own workflow instance.
    """
    _prompt = PromptExecutor(id="hello_prompt")
    _llm = LLMExecutor(id="llm")
    return (
        WorkflowBuilder(name="BasicWorkflow", start_executor=_prompt)
        .add_edge(_prompt, _llm)
        .build()
    )


async def main():
    workflow = create_workflow()
    result = await workflow.run("Hello World!")
    print(result.get_outputs()[0])


if __name__ == "__main__":
    asyncio.run(main())

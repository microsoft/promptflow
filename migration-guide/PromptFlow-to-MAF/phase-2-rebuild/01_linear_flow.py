"""
Migrates the simplest Prompt Flow pattern: Input node → LLM node.

Prompt Flow equivalent:
    [Input node] --> [LLM node]
"""

import asyncio
import os

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

load_dotenv()


class InputExecutor(Executor):
    """Replaces the Prompt Flow Input node.

    WorkflowContext[str] sends a str to the next executor via ctx.send_message().
    """

    @handler
    async def receive(self, question: str, ctx: WorkflowContext[str]) -> None:
        await ctx.send_message(question.strip())


class LLMExecutor(Executor):
    """Replaces the Prompt Flow LLM node.

    WorkflowContext[Never, str]:
      - Never → does not send messages to downstream executors
      - str   → yields a str as the final workflow output via ctx.yield_output()

    FoundryChatClient connects to a Microsoft Foundry project endpoint.
    It reads FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL from the environment.

    The 'instructions' parameter replaces the system prompt template in the PF LLM node.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["FOUNDRY_MODEL"],
            credential=DefaultAzureCredential(),
        )
        self._agent = Agent(
            client=client,
            name="QAAgent",
            instructions="You are a helpful assistant. Answer concisely.",
        )

    @handler
    async def call_llm(self, question: str, ctx: WorkflowContext[Never, str]) -> None:
        result = await self._agent.run(question)
        await ctx.yield_output(result)


_input = InputExecutor(id="input")
_llm = LLMExecutor(id="llm")

workflow = (
    WorkflowBuilder(name="LinearWorkflow", start_executor=_input)
    .add_edge(_input, _llm)
    .build()
)


async def main():
    result = await workflow.run("What is retrieval-augmented generation?")
    print(result.get_outputs()[0])


if __name__ == "__main__":
    asyncio.run(main())

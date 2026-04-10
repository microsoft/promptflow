"""
Migrates the simplest Prompt Flow pattern: Input node → LLM node.

Prompt Flow equivalent:
    [Input node] --> [LLM node]
"""

import asyncio

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.azure import AzureOpenAIChatClient

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

    AzureOpenAIChatClient reads from environment automatically:
      AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME

    The 'instructions' parameter replaces the system prompt template in the PF LLM node.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._agent = AzureOpenAIChatClient().as_agent(
            name="QAAgent",
            instructions="You are a helpful assistant. Answer concisely.",
        )

    @handler
    async def call_llm(self, question: str, ctx: WorkflowContext[Never, str]) -> None:
        result = await self._agent.run(question)
        await ctx.yield_output(result)


workflow = (
    WorkflowBuilder(name="LinearWorkflow")
    .register_executor(lambda: InputExecutor(id="input"), name="Input")
    .register_executor(lambda: LLMExecutor(id="llm"), name="LLM")
    .add_edge("Input", "LLM")
    .set_start_executor("Input")
    .build()
)


async def main():
    result = await workflow.run("What is retrieval-augmented generation?")
    print(result.get_outputs()[0])


if __name__ == "__main__":
    asyncio.run(main())

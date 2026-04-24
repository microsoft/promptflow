"""
Basic Chat — Microsoft Agent Framework version.

Migrated from the Prompt Flow chat-basic example.
Original flow: Input (question + chat_history) → LLM node → answer

This workflow uses a single Agent with FoundryChatClient to replicate
the same chat behaviour: a helpful assistant that remembers conversation
history and responds to user questions.
"""

import asyncio
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()


@dataclass
class ChatInput:
    """Mirrors the Prompt Flow inputs: question + chat_history."""

    question: str
    chat_history: list | None = None


class InputExecutor(Executor):
    """Replaces the Prompt Flow Input node.

    Accepts a ChatInput, formats the conversation history into the prompt,
    and forwards the assembled prompt string to the LLM executor.
    """

    @handler
    async def receive(self, chat_input: ChatInput, ctx: WorkflowContext[str]) -> None:
        parts = []

        # Replay chat history as a formatted conversation
        if chat_input.chat_history:
            for turn in chat_input.chat_history:
                parts.append(f"User: {turn['inputs']['question']}")
                parts.append(f"Assistant: {turn['outputs']['answer']}")

        # Append the current user question
        parts.append(chat_input.question)

        await ctx.send_message("\n".join(parts))


class ChatExecutor(Executor):
    """Replaces the Prompt Flow LLM (chat) node.

    Uses OpenAIChatClient (Azure routing) + Agent with the same system prompt
    as the original chat.jinja2 template: "You are a helpful assistant."
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="ChatAgent",
            instructions="You are a helpful assistant.",
        )

    @handler
    async def call_llm(self, question: str, ctx: WorkflowContext[Never, str]) -> None:
        response = await self._agent.run(question)
        await ctx.yield_output(response.text)


# ── Build the workflow ────────────────────────────────────────────────────────
_input = InputExecutor(id="input")
_chat = ChatExecutor(id="chat")

workflow = (
    WorkflowBuilder(name="BasicChatWorkflow", start_executor=_input)
    .add_edge(_input, _chat)
    .build()
)


async def main():
    # Simple single-turn test (no history)
    result = await workflow.run(ChatInput(question="What is ChatGPT?"))
    print("Answer:", result.get_outputs()[0])
    print()

    # Multi-turn test (with chat history)
    history = [
        {
            "inputs": {"question": "What is ChatGPT?"},
            "outputs": {"answer": "ChatGPT is a large language model chatbot developed by OpenAI."},
        }
    ]
    result = await workflow.run(
        ChatInput(
            question="What is the difference between ChatGPT and GPT-4?",
            chat_history=history,
        )
    )
    print("Answer:", result.get_outputs()[0])


if __name__ == "__main__":
    asyncio.run(main())

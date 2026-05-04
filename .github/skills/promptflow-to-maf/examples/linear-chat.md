# Example: Linear Chat Flow

> Reference example. Read when you want a full template for a single-LLM-node flow with chat history.

This converts a Prompt Flow with one LLM node and chat history:

```python
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
    question: str
    chat_history: list | None = None

class InputExecutor(Executor):
    @handler
    async def receive(self, chat_input: ChatInput, ctx: WorkflowContext[str]) -> None:
        parts = []
        if chat_input.chat_history:
            for turn in chat_input.chat_history:
                parts.append(f"User: {turn['inputs']['question']}")
                parts.append(f"Assistant: {turn['outputs']['answer']}")
        parts.append(chat_input.question)
        await ctx.send_message("\n".join(parts))

class ChatExecutor(Executor):
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

def create_workflow():
    """Create a fresh workflow instance.

    MAF workflows do not support concurrent execution, so each
    concurrent caller needs its own workflow instance.
    """
    _input = InputExecutor(id="input")
    _chat = ChatExecutor(id="chat")
    return (
        WorkflowBuilder(name="BasicChatWorkflow", start_executor=_input)
        .add_edge(_input, _chat)
        .build()
    )

async def main():
    workflow = create_workflow()
    result = await workflow.run(ChatInput(question="What is ChatGPT?"))
    print(result.get_outputs()[0])

if __name__ == "__main__":
    asyncio.run(main())
```

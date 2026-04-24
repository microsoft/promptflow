import asyncio
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

_INTENT_SYSTEM_PROMPT = """\
You are given a list of orders with item_numbers from a customer and a statement from the customer. \
It is your job to identify the intent that the customer has with their statement. \
Possible intents can be: "product return", "product exchange", "general question", "product question", "other"."""

_INTENT_USER_TEMPLATE = """\
In triple backticks below is the customer information and a list of orders.

```
{customer_info}
```

In triple backticks below are the is the chat history with customer statements and replies from the customer service agent:

```
{history}
```

What is the customer's `intent:` here?

"product return", "exchange product", "general question", "product question" or "other"?

Reply with only the intent string."""


@dataclass
class IntentInput:
    history: str
    customer_info: str


class PromptExecutor(Executor):
    @handler
    async def receive(self, intent_input: IntentInput, ctx: WorkflowContext[str]) -> None:
        prompt = _INTENT_USER_TEMPLATE.format(
            customer_info=intent_input.customer_info,
            history=intent_input.history,
        )
        await ctx.send_message(prompt)


class ExtractIntentExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="IntentAgent",
            instructions=_INTENT_SYSTEM_PROMPT,
        )

    @handler
    async def extract(self, prompt: str, ctx: WorkflowContext[Never, str]) -> None:
        response = await self._agent.run(prompt)
        await ctx.yield_output(response.text)


_prompt = PromptExecutor(id="chat_prompt")
_extract = ExtractIntentExecutor(id="extract_intent")

workflow = (
    WorkflowBuilder(name="CustomerIntentWorkflow", start_executor=_prompt)
    .add_edge(_prompt, _extract)
    .build()
)


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

import asyncio
import os
import re
from dataclasses import dataclass, field

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Content, Executor, Message, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

INSTRUCTIONS = "You are a helpful assistant."

# Matches Prompt Flow image key like "data:image/png;url"
_IMAGE_KEY_RE = re.compile(r"^data:image/[^;]+;url$")
# Matches Prompt Flow image string like "data:image/png;url: https://..."
_IMAGE_STR_RE = re.compile(r"^data:image/[^;]+;url:\s*(.+)$")


def _parse_question_parts(parts: list) -> list[Content | str]:
    """Convert Prompt Flow multimodal question parts to Content objects.

    Supports two formats:
    - dict: {"data:image/png;url": "https://example.com/img.png"}
    - string: "data:image/png;url: https://example.com/img.png"
    """
    contents: list[Content | str] = []
    for part in parts:
        if isinstance(part, dict):
            for key, url in part.items():
                if _IMAGE_KEY_RE.match(key):
                    contents.append(Content.from_uri(url, media_type="image/png"))
        elif isinstance(part, str):
            m = _IMAGE_STR_RE.match(part)
            if m:
                contents.append(Content.from_uri(m.group(1).strip(), media_type="image/png"))
            else:
                contents.append(part)
        else:
            contents.append(str(part))
    return contents


@dataclass
class ChatInput:
    question: list  # e.g. [{"data:image/png;url": "<url>"}, "How many colors?"]
    chat_history: list = field(default_factory=list)


class InputExecutor(Executor):
    """Builds a multimodal Message from chat history and the question."""

    @handler
    async def receive(self, chat_input: ChatInput, ctx: WorkflowContext[Message]) -> None:
        contents: list[Content | str] = []
        # Format chat history as text
        if chat_input.chat_history:
            for turn in chat_input.chat_history:
                contents.append(f"User: {turn['inputs']['question']}")
                contents.append(f"Assistant: {turn['outputs']['answer']}")
        # Parse multimodal question parts (image URLs become Content.from_uri)
        contents.extend(_parse_question_parts(chat_input.question))
        await ctx.send_message(Message("user", contents))


class ChatExecutor(Executor):
    """Calls GPT-4V with the multimodal Message."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4v"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="ChatImageAgent",
            instructions=INSTRUCTIONS,
        )

    @handler
    async def call_llm(self, prompt: Message, ctx: WorkflowContext[Never, str]) -> None:
        response = await self._agent.run(prompt)
        await ctx.yield_output(response.text)


_input = InputExecutor(id="input")
_chat = ChatExecutor(id="chat")

workflow = (
    WorkflowBuilder(name="ChatWithImageWorkflow", start_executor=_input)
    .add_edge(_input, _chat)
    .build()
)


async def main():
    result = await workflow.run(
        ChatInput(
            question=[
                "How many colors can you see?",
                {"data:image/png;url": "https://uhf.microsoft.com/images/microsoft/RE1Mu3b.png"},
            ]
        )
    )
    print("Answer:", result.get_outputs()[0])


if __name__ == "__main__":
    asyncio.run(main())

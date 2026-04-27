"""MAF workflow converted from chat-with-pdf/flow.dag.yaml.single-node

Graph: SetupEnvExecutor -> ChatWithPdfExecutor

SetupEnvExecutor: creates required directories (replaces PF connection setup)
ChatWithPdfExecutor: downloads PDF, builds index, rewrites question, finds context, runs QnA
"""

import asyncio
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from chat_with_pdf.main import chat_with_pdf
from chat_with_pdf.constants import PDF_DIR, INDEX_DIR

load_dotenv()


@dataclass
class ChatInput:
    question: str
    pdf_url: str = "https://arxiv.org/pdf/1810.04805.pdf"
    chat_history: list = field(default_factory=list)


def _convert_chat_history(history: list) -> list[dict]:
    messages = []
    for item in history:
        messages.append({"role": "user", "content": item["inputs"]["question"]})
        messages.append({"role": "assistant", "content": item["outputs"]["answer"]})
    return messages


class SetupEnvExecutor(Executor):
    @handler
    async def setup(self, chat_input: ChatInput, ctx: WorkflowContext[ChatInput]) -> None:
        os.makedirs(PDF_DIR, exist_ok=True)
        os.makedirs(INDEX_DIR, exist_ok=True)
        await ctx.send_message(chat_input)


class ChatWithPdfExecutor(Executor):
    @handler
    async def run(self, chat_input: ChatInput, ctx: WorkflowContext[Never, dict]) -> None:
        history = _convert_chat_history(chat_input.chat_history)
        stream, context = chat_with_pdf(chat_input.question, chat_input.pdf_url, history)
        answer = "".join(stream)
        await ctx.yield_output({"answer": answer, "context": context})


def create_workflow():
    """Create a fresh workflow instance.

    MAF workflows do not support concurrent execution, so each
    concurrent caller needs its own workflow instance.
    """
    _setup = SetupEnvExecutor(id="setup_env")
    _chat = ChatWithPdfExecutor(id="chat_with_pdf")
    return (
        WorkflowBuilder(name="ChatWithPdfSingleNode", start_executor=_setup)
        .add_edge(_setup, _chat)
        .build()
    )


async def main():
    workflow = create_workflow()
    result = await workflow.run(
        ChatInput(question="what NLP tasks does it perform well?")
    )
    output = result.get_outputs()[0]
    print(f"Answer: {output['answer']}")
    print(f"Context: {output['context']}")


if __name__ == "__main__":
    asyncio.run(main())

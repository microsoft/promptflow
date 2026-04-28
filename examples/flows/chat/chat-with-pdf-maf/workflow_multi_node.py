"""MAF workflow converted from chat-with-pdf/flow.dag.yaml.multi-node

Graph:
  InputExecutor ──fan-out──> DownloadExecutor -> BuildIndexExecutor ──┐
                    └──────> RewriteQuestionExecutor ─────────────────┘──fan-in──> QnaExecutor

InputExecutor: sets up directories, fans out ChatInput
DownloadExecutor: downloads PDF from url
BuildIndexExecutor: builds FAISS index from PDF
RewriteQuestionExecutor: rewrites question using chat history
QnaExecutor: finds context from index, runs QnA, yields output
"""

import asyncio
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from chat_with_pdf.download import download
from chat_with_pdf.build_index import create_faiss_index
from chat_with_pdf.rewrite_question import rewrite_question
from chat_with_pdf.find_context import find_context
from chat_with_pdf.qna import qna
from chat_with_pdf.constants import PDF_DIR, INDEX_DIR

load_dotenv()


@dataclass
class ChatInput:
    question: str
    pdf_url: str = "https://arxiv.org/pdf/1810.04805.pdf"
    chat_history: list = field(default_factory=list)


@dataclass
class QnaBranchResult:
    index_path: str = ""
    rewritten_question: str = ""
    chat_history: list = field(default_factory=list)


def _convert_chat_history(history: list) -> list[dict]:
    messages = []
    for item in history:
        messages.append({"role": "user", "content": item["inputs"]["question"]})
        messages.append({"role": "assistant", "content": item["outputs"]["answer"]})
    return messages


class InputExecutor(Executor):
    @handler
    async def receive(self, chat_input: ChatInput, ctx: WorkflowContext[ChatInput]) -> None:
        os.makedirs(PDF_DIR, exist_ok=True)
        os.makedirs(INDEX_DIR, exist_ok=True)
        await ctx.send_message(chat_input)


class DownloadExecutor(Executor):
    @handler
    async def run(self, chat_input: ChatInput, ctx: WorkflowContext[str]) -> None:
        pdf_path = download(chat_input.pdf_url)
        await ctx.send_message(pdf_path)


class BuildIndexExecutor(Executor):
    @handler
    async def run(self, pdf_path: str, ctx: WorkflowContext[QnaBranchResult]) -> None:
        index_path = create_faiss_index(pdf_path)
        await ctx.send_message(QnaBranchResult(index_path=index_path))


class RewriteQuestionExecutor(Executor):
    @handler
    async def run(self, chat_input: ChatInput, ctx: WorkflowContext[QnaBranchResult]) -> None:
        rewritten = rewrite_question(chat_input.question, chat_input.chat_history)
        await ctx.send_message(QnaBranchResult(
            rewritten_question=rewritten,
            chat_history=chat_input.chat_history,
        ))


class QnaExecutor(Executor):
    @handler
    async def run(self, results: list[QnaBranchResult], ctx: WorkflowContext[Never, dict]) -> None:
        index_path = ""
        rewritten_question = ""
        chat_history = []
        for r in results:
            if r.index_path:
                index_path = r.index_path
            if r.rewritten_question:
                rewritten_question = r.rewritten_question
            if r.chat_history:
                chat_history = r.chat_history

        prompt, context = find_context(rewritten_question, index_path)
        history_messages = _convert_chat_history(chat_history)
        stream = qna(prompt, history_messages)
        answer = "".join(stream)
        await ctx.yield_output({"answer": answer, "context": context})


def create_workflow():
    """Create a fresh workflow instance.

    MAF workflows do not support concurrent execution, so each
    concurrent caller needs its own workflow instance.
    """
    _input = InputExecutor(id="input")
    _download = DownloadExecutor(id="download")
    _build_index = BuildIndexExecutor(id="build_index")
    _rewrite = RewriteQuestionExecutor(id="rewrite_question")
    _qna = QnaExecutor(id="qna")
    return (
        WorkflowBuilder(name="ChatWithPdfMultiNode", start_executor=_input)
        .add_fan_out_edges(_input, [_download, _rewrite])
        .add_edge(_download, _build_index)
        .add_fan_in_edges([_build_index, _rewrite], _qna)
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

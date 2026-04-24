import asyncio
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from chat_with_pdf.build_index import create_faiss_index
from chat_with_pdf.constants import PDF_DIR, INDEX_DIR
from chat_with_pdf.download import download
from chat_with_pdf.find_context import find_context
from chat_with_pdf.qna import qna
from chat_with_pdf.rewrite_question import rewrite_question
from chat_with_pdf.utils.lock import acquire_lock

load_dotenv()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PdfChatInput:
    question: str
    pdf_url: str = "https://arxiv.org/pdf/1810.04805.pdf"
    chat_history: list = field(default_factory=list)
    config: dict = field(default_factory=lambda: {
        "EMBEDDING_MODEL_DEPLOYMENT_NAME": os.environ.get("EMBEDDING_MODEL_DEPLOYMENT_NAME", "text-embedding-ada-002"),
        "CHAT_MODEL_DEPLOYMENT_NAME": os.environ.get("CHAT_MODEL_DEPLOYMENT_NAME", "gpt-4"),
        "PROMPT_TOKEN_LIMIT": os.environ.get("PROMPT_TOKEN_LIMIT", "3000"),
        "MAX_COMPLETION_TOKENS": os.environ.get("MAX_COMPLETION_TOKENS", "1024"),
        "VERBOSE": os.environ.get("VERBOSE", "true"),
        "CHUNK_SIZE": os.environ.get("CHUNK_SIZE", "1024"),
        "CHUNK_OVERLAP": os.environ.get("CHUNK_OVERLAP", "64"),
    })


@dataclass
class BranchResult:
    index_path: str | None = None
    rewritten_question: str | None = None
    chat_history: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


def _to_chatml(history: list) -> list[dict]:
    messages = []
    for item in history:
        messages.append({"role": "user", "content": item["inputs"]["question"]})
        messages.append({"role": "assistant", "content": item["outputs"]["answer"]})
    return messages


class InputExecutor(Executor):
    """Sets environment variables from config and creates working directories."""

    @handler
    async def receive(self, inp: PdfChatInput, ctx: WorkflowContext[PdfChatInput]) -> None:
        for key, value in inp.config.items():
            os.environ[key] = str(value)

        base_dir = os.path.join(os.path.dirname(__file__), "chat_with_pdf")
        with acquire_lock(os.path.join(base_dir, "create_folder.lock")):
            os.makedirs(PDF_DIR, exist_ok=True)
            os.makedirs(INDEX_DIR, exist_ok=True)

        await ctx.send_message(inp)


class IndexExecutor(Executor):
    """Downloads PDF and builds FAISS index (merges download_tool + build_index_tool)."""

    @handler
    async def process(self, inp: PdfChatInput, ctx: WorkflowContext[BranchResult]) -> None:
        pdf_path = download(inp.pdf_url)
        index_path = create_faiss_index(pdf_path)
        await ctx.send_message(BranchResult(index_path=index_path))


class RewriteExecutor(Executor):
    """Rewrites question using chat history for better context retrieval."""

    @handler
    async def process(self, inp: PdfChatInput, ctx: WorkflowContext[BranchResult]) -> None:
        rewritten = rewrite_question(inp.question, _to_chatml(inp.chat_history))
        await ctx.send_message(BranchResult(
            rewritten_question=rewritten,
            chat_history=inp.chat_history,
        ))


class ContextAndQnAExecutor(Executor):
    """Fan-in: finds relevant context from index, then generates answer."""

    @handler
    async def process(self, results: list[BranchResult], ctx: WorkflowContext[Never, dict]) -> None:
        index_path = None
        rewritten_question = None
        chat_history: list = []
        for r in results:
            if r.index_path:
                index_path = r.index_path
            if r.rewritten_question:
                rewritten_question = r.rewritten_question
            if r.chat_history:
                chat_history = r.chat_history

        prompt, context = find_context(rewritten_question, index_path)

        stream = qna(prompt, _to_chatml(chat_history))
        answer = "".join(stream)

        await ctx.yield_output({
            "answer": answer,
            "context": [c.text for c in context],
        })


# ---------------------------------------------------------------------------
# Workflow: input → fan_out[index, rewrite] → fan_in → context_qna
# ---------------------------------------------------------------------------

_input = InputExecutor(id="input")
_index = IndexExecutor(id="index")
_rewrite = RewriteExecutor(id="rewrite")
_context_qna = ContextAndQnAExecutor(id="context_qna")

workflow = (
    WorkflowBuilder(name="ChatWithPdfWorkflow", start_executor=_input)
    .add_fan_out_edges(_input, [_index, _rewrite])
    .add_fan_in_edges([_index, _rewrite], _context_qna)
    .build()
)


async def main():
    result = await workflow.run(
        PdfChatInput(
            question="What is BERT?",
            pdf_url="https://arxiv.org/pdf/1810.04805.pdf",
        )
    )
    output = result.get_outputs()[0]
    print(f"Answer: {output['answer']}")
    print(f"Context: {output['context']}")


if __name__ == "__main__":
    asyncio.run(main())

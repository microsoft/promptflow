"""
Chat with PDF Agent - Microsoft Agent Framework Workflow version.

This replicates the promptflow DAG flow using Agent Framework's WorkflowBuilder
to enforce a fixed execution order, matching the original DAG exactly:

    [input] -> download -> build_index -> rewrite_question -> find_context -> qna -> [output]

Each promptflow node maps to an Executor in the workflow graph.
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing_extensions import Never

from dotenv import load_dotenv

# Add project root to path so chat_with_pdf package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_framework import (
    Executor,
    Message,
    WorkflowAgent,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)

from chat_with_pdf.utils.lock import acquire_lock
from chat_with_pdf.download import download
from chat_with_pdf.build_index import create_faiss_index
from chat_with_pdf.find_context import find_context
from chat_with_pdf.rewrite_question import rewrite_question
from chat_with_pdf.qna import qna

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_with_pdf")


# ---------------------------------------------------------------------------
# Message types passed between workflow executors
# ---------------------------------------------------------------------------

@dataclass
class ChatInput:
    """Initial input to the workflow."""
    question: str
    pdf_url: str
    chat_history: list


@dataclass
class Downloaded:
    """Output of DownloadExecutor — carries the local PDF path forward."""
    question: str
    pdf_url: str
    pdf_path: str
    chat_history: list


@dataclass
class Indexed:
    """Output of BuildIndexExecutor — carries the index path forward."""
    question: str
    index_path: str
    chat_history: list


@dataclass
class QuestionRewritten:
    """Output of RewriteQuestionExecutor — carries the rewritten question."""
    rewritten_question: str
    index_path: str
    chat_history: list


@dataclass
class ContextFound:
    """Output of FindContextExecutor — carries the QnA prompt and context."""
    prompt: str
    context: list
    chat_history: list


@dataclass
class ChatOutput:
    """Final workflow output."""
    answer: str
    context: list


# ---------------------------------------------------------------------------
# Executors — one per promptflow DAG node
# ---------------------------------------------------------------------------

class DownloadExecutor(Executor):
    """Mirrors the download_tool node: downloads PDF from URL.
    Accepts list[Message] from WorkflowAgent (the entry point).
    """

    @handler
    async def handle(self, msg: list[Message], ctx: WorkflowContext[Downloaded]) -> None:
        # Parse the structured JSON input from the user message
        user_text = ""
        for m in msg:
            if m.role == "user":
                user_text = m.text or ""
                break

        data = json.loads(user_text)
        pdf_path = download(data["pdf_url"])
        await ctx.send_message(Downloaded(
            question=data["question"],
            pdf_url=data["pdf_url"],
            pdf_path=pdf_path,
            chat_history=data.get("chat_history", []),
        ))


class BuildIndexExecutor(Executor):
    """Mirrors the build_index_tool node: builds FAISS index from PDF."""

    @handler
    async def handle(self, msg: Downloaded, ctx: WorkflowContext[Indexed]) -> None:
        index_path = create_faiss_index(msg.pdf_path)
        await ctx.send_message(Indexed(
            question=msg.question,
            index_path=index_path,
            chat_history=msg.chat_history,
        ))


class RewriteQuestionExecutor(Executor):
    """Mirrors the rewrite_question_tool node: rewrites question with history context."""

    @handler
    async def handle(self, msg: Indexed, ctx: WorkflowContext[QuestionRewritten]) -> None:
        chatml_history = []
        for item in msg.chat_history:
            chatml_history.append({"role": "user", "content": item["inputs"]["question"]})
            chatml_history.append({"role": "assistant", "content": item["outputs"]["answer"]})

        rewritten_q = rewrite_question(msg.question, chatml_history)
        await ctx.send_message(QuestionRewritten(
            rewritten_question=rewritten_q,
            index_path=msg.index_path,
            chat_history=chatml_history,
        ))


class FindContextExecutor(Executor):
    """Mirrors the find_context_tool node: retrieves relevant context from FAISS index."""

    @handler
    async def handle(self, msg: QuestionRewritten, ctx: WorkflowContext[ContextFound]) -> None:
        prompt, snippets = find_context(msg.rewritten_question, msg.index_path)
        await ctx.send_message(ContextFound(
            prompt=prompt,
            context=[s.text for s in snippets],
            chat_history=msg.chat_history,
        ))


class QnAExecutor(Executor):
    """Mirrors the qna_tool node: generates the final answer using LLM."""

    @handler
    async def handle(self, msg: ContextFound, ctx: WorkflowContext[Never, ChatOutput]) -> None:
        stream = qna(msg.prompt, msg.chat_history)
        answer = ""
        for chunk in stream:
            answer += chunk

        await ctx.yield_output(ChatOutput(
            answer=answer,
            context=msg.context,
        ))


# ---------------------------------------------------------------------------
# Environment setup (mirrors setup_env node from promptflow)
# ---------------------------------------------------------------------------

def setup_env(config: dict = None):
    """Load .env and apply runtime config overrides."""
    load_dotenv(override=False)

    if config:
        for key, value in config.items():
            os.environ[key] = str(value)

    with acquire_lock(os.path.join(BASE_DIR, "create_folder.lock")):
        pdfs_dir = os.path.join(BASE_DIR, ".pdfs")
        index_dir = os.path.join(BASE_DIR, ".index", ".pdfs")
        if not os.path.exists(pdfs_dir):
            os.mkdir(pdfs_dir)
        if not os.path.exists(index_dir):
            os.makedirs(index_dir)


# ---------------------------------------------------------------------------
# Workflow & Agent creation
# ---------------------------------------------------------------------------

def create_workflow_agent(config: dict = None) -> WorkflowAgent:
    """Create a WorkflowAgent with a fixed DAG matching the promptflow flow."""
    setup_env(config)

    # Create executor instances (one per DAG node)
    download_exec = DownloadExecutor(id="download")
    build_index_exec = BuildIndexExecutor(id="build_index")
    rewrite_question_exec = RewriteQuestionExecutor(id="rewrite_question")
    find_context_exec = FindContextExecutor(id="find_context")
    qna_exec = QnAExecutor(id="qna")

    # Build the workflow graph:
    # download -> build_index -> rewrite_question -> find_context -> qna
    workflow = (
        WorkflowBuilder(
            start_executor=download_exec,
            name="chat-with-pdf",
            description="Chat with PDF — fixed DAG workflow matching promptflow",
        )
        .add_edge(download_exec, build_index_exec)
        .add_edge(build_index_exec, rewrite_question_exec)
        .add_edge(rewrite_question_exec, find_context_exec)
        .add_edge(find_context_exec, qna_exec)
        .build()
    )

    return WorkflowAgent(
        workflow=workflow,
        name="ChatWithPDF",
        description="Answers questions about PDF documents using a fixed RAG pipeline.",
    )


async def chat_with_pdf(
    question: str,
    pdf_url: str,
    chat_history: list = None,
    config: dict = None,
) -> dict:
    """
    Run the chat-with-pdf workflow — equivalent to one execution of the
    promptflow DAG flow, with a fixed execution order.

    Returns:
        dict with "answer" and "context" keys, matching the promptflow outputs.
    """
    if chat_history is None:
        chat_history = []

    agent = create_workflow_agent(config)

    # WorkflowAgent expects string or Message input — send structured JSON
    user_input = json.dumps({
        "question": question,
        "pdf_url": pdf_url,
        "chat_history": chat_history,
    })

    response = await agent.run(user_input)

    # WorkflowAgent converts yield_output(ChatOutput(...)) into a Message whose
    # raw_representation is the original ChatOutput dataclass.  The text property
    # only contains str(ChatOutput(...)), so we extract from raw_representation.
    if response.messages:
        for msg in response.messages:
            if isinstance(msg.raw_representation, ChatOutput):
                return {"answer": msg.raw_representation.answer, "context": msg.raw_representation.context}
        # Fallback: return concatenated text if no ChatOutput found
        return {"answer": response.text, "context": []}

    return {"answer": "", "context": []}


if __name__ == "__main__":
    result = asyncio.run(chat_with_pdf(
        question="what is BERT?",
        pdf_url="https://arxiv.org/pdf/1810.04805.pdf",
        chat_history=[],
    ))
    print(result["answer"])

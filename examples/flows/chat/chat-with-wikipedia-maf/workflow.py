import asyncio
import os
import re
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial

import bs4
import requests
from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient

load_dotenv()

# ---------------------------------------------------------------------------
# Prompt templates (from .jinja2 files)
# ---------------------------------------------------------------------------

EXTRACT_QUERY_INSTRUCTIONS = """\
You are an AI assistant reading the transcript of a conversation between an AI and a human. \
Given an input question and conversation history, infer user real intent.

The conversation history is provided just in case of a context \
(e.g. "What is this?" where "this" is defined in previous conversation).

Return the output as query used for next round user message."""

AUGMENTED_CHAT_INSTRUCTIONS = """\
You are a chatbot having a conversation with a human.
Given the following extracted parts of a long document and a question, create a final answer with references ("SOURCES").
If you don't know the answer, just say that you don't know. Don't try to make up an answer.
ALWAYS return a "SOURCES" part in your answer."""

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ChatInput:
    question: str
    chat_history: list = field(default_factory=list)


@dataclass
class QueryWithContext:
    question: str
    chat_history: list
    contexts: str


# ---------------------------------------------------------------------------
# Wikipedia helper functions (from get_wiki_url.py, search_result_from_url.py,
# process_search_result.py)
# ---------------------------------------------------------------------------

_session = requests.Session()


def _decode_str(string):
    return string.encode().decode("unicode-escape").encode("latin1").decode("utf-8")


def _remove_nested_parentheses(string):
    pattern = r"\([^()]+\)"
    while re.search(pattern, string):
        string = re.sub(pattern, "", string)
    return string


def get_wiki_url(entity: str, count: int = 2) -> list[str]:
    url = f"https://en.wikipedia.org/w/index.php?search={entity}"
    url_list: list[str] = []
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.35"
            )
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            mw_divs = soup.find_all("div", {"class": "mw-search-result-heading"})
            if mw_divs:
                result_titles = [_decode_str(div.get_text().strip()) for div in mw_divs]
                result_titles = [_remove_nested_parentheses(t) for t in result_titles]
                url_list.extend(
                    f"https://en.wikipedia.org/w/index.php?search={t}" for t in result_titles
                )
            else:
                page_content = [p.get_text().strip() for p in soup.find_all("p") + soup.find_all("ul")]
                if any("may refer to:" in p for p in page_content):
                    url_list.extend(get_wiki_url("[" + entity + "]"))
                else:
                    url_list.append(url)
        return url_list[:count]
    except Exception as e:
        print(f"Get url failed with error: {e}")
        return url_list


def _get_page_sentence(page: str, count: int = 10) -> str:
    paragraphs = [p.strip() for p in page.split("\n") if p.strip()]
    sentences: list[str] = []
    for p in paragraphs:
        sentences += p.split(". ")
    sentences = [s.strip() + "." for s in sentences if s.strip()]
    return " ".join(sentences[:count])


def _fetch_text_content_from_url(url: str, count: int = 10) -> tuple[str, str]:
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.35"
            )
        }
        delay = random.uniform(0, 0.5)
        time.sleep(delay)
        response = _session.get(url, headers=headers)
        if response.status_code == 200:
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            page_content = [p.get_text().strip() for p in soup.find_all("p") + soup.find_all("ul")]
            page = ""
            for content in page_content:
                if len(content.split(" ")) > 2:
                    page += _decode_str(content)
                if not content.endswith("\n"):
                    page += "\n"
            return (url, _get_page_sentence(page, count=count))
        return (url, "No available content")
    except Exception as e:
        print(f"Get url failed with error: {e}")
        return (url, "No available content")


def search_result_from_url(url_list: list[str], count: int = 10) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    fn = partial(_fetch_text_content_from_url, count=count)
    with ThreadPoolExecutor(max_workers=5) as executor:
        for r in executor.map(fn, url_list):
            results.append(r)
    return results


def process_search_result(search_result: list[tuple[str, str]]) -> str:
    context = []
    for url, content in search_result:
        context.append({"Content": content, "Source": url})
    return "\n\n".join(f"Content: {c['Content']}\nSource: {c['Source']}" for c in context)


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


class InputExecutor(Executor):
    """Passes the ChatInput through to the next stage."""

    @handler
    async def receive(self, chat_input: ChatInput, ctx: WorkflowContext[ChatInput]) -> None:
        await ctx.send_message(chat_input)


class ExtractQueryExecutor(Executor):
    """LLM node: extracts a search query from the user question + chat history."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-35-turbo"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="ExtractQueryAgent",
            instructions=EXTRACT_QUERY_INSTRUCTIONS,
        )

    @handler
    async def extract(self, chat_input: ChatInput, ctx: WorkflowContext[ChatInput]) -> None:
        # Build the prompt with history
        parts: list[str] = []
        for turn in chat_input.chat_history:
            parts.append(f"Human: {turn['inputs']['question']}")
            parts.append(f"AI: {turn['outputs']['answer']}")
        parts.append(f"Human: {chat_input.question}")
        parts.append("\nOutput:")

        response = await self._agent.run("\n".join(parts))
        # Replace the question with the extracted query for downstream
        await ctx.send_message(
            ChatInput(
                question=response.text.strip(),
                chat_history=chat_input.chat_history,
            )
        )


class WikiSearchExecutor(Executor):
    """Python node: searches Wikipedia and retrieves page content."""

    @handler
    async def search(self, chat_input: ChatInput, ctx: WorkflowContext[QueryWithContext]) -> None:
        entity = chat_input.question
        urls = get_wiki_url(entity, count=2)
        search_results = search_result_from_url(urls, count=10)
        contexts = process_search_result(search_results)
        await ctx.send_message(
            QueryWithContext(
                question=chat_input.question,
                chat_history=chat_input.chat_history,
                contexts=contexts,
            )
        )


class AugmentedChatExecutor(Executor):
    """LLM node: answers the question using Wikipedia context."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-35-turbo"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="AugmentedChatAgent",
            instructions=AUGMENTED_CHAT_INSTRUCTIONS,
        )

    @handler
    async def answer(self, qc: QueryWithContext, ctx: WorkflowContext[Never, str]) -> None:
        parts: list[str] = [qc.contexts, ""]
        for turn in qc.chat_history:
            parts.append(f"User: {turn['inputs']['question']}")
            parts.append(f"Assistant: {turn['outputs']['answer']}")
        parts.append(qc.question)

        response = await self._agent.run("\n".join(parts))
        await ctx.yield_output(response.text)


# ---------------------------------------------------------------------------
# Workflow: input → extract_query → wiki_search → augmented_chat → output
# ---------------------------------------------------------------------------

_input = InputExecutor(id="input")
_extract = ExtractQueryExecutor(id="extract_query")
_wiki = WikiSearchExecutor(id="wiki_search")
_chat = AugmentedChatExecutor(id="augmented_chat")

workflow = (
    WorkflowBuilder(name="ChatWithWikipediaWorkflow", start_executor=_input)
    .add_edge(_input, _extract)
    .add_edge(_extract, _wiki)
    .add_edge(_wiki, _chat)
    .build()
)


async def main():
    result = await workflow.run(ChatInput(question="What is ChatGPT?"))
    print("Answer:", result.get_outputs()[0])


if __name__ == "__main__":
    asyncio.run(main())

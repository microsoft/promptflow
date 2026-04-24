import asyncio
import json
import os
from dataclasses import dataclass

import bs4
import requests
from dotenv import load_dotenv
from typing_extensions import Never

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.openai import OpenAIChatClient, OpenAIChatOptions

load_dotenv()

_SUMMARIZE_SYSTEM_PROMPT = """\
Please summarize the following text in one paragraph. 100 words.
Do not add any information that is not in the text."""

_CLASSIFY_SYSTEM_PROMPT = """\
Your task is to classify a given url into one of the following categories:
Movie, App, Academic, Channel, Profile, PDF or None based on the text content information.
The classification will be based on the url, the webpage text content summary, or both."""

_EXAMPLES = [
    {
        "url": "https://play.google.com/store/apps/details?id=com.spotify.music",
        "text_content": (
            "Spotify is a free music and podcast streaming app with millions of songs, albums, and "
            "original podcasts. It also offers audiobooks, so users can enjoy thousands of stories. "
            "It has a variety of features such as creating and sharing music playlists, discovering "
            "new music, and listening to popular and exclusive podcasts. It also has a Premium "
            "subscription option which allows users to download and listen offline, and access "
            "ad-free music. It is available on all devices and has a variety of genres and artists "
            "to choose from."
        ),
        "category": "App",
        "evidence": "Both",
    },
    {
        "url": "https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw",
        "text_content": (
            "NFL Sunday Ticket is a service offered by Google LLC that allows users to watch NFL "
            "games on YouTube. It is available in 2023 and is subject to the terms and privacy policy "
            "of Google LLC. It is also subject to YouTube's terms of use and any applicable laws."
        ),
        "category": "Channel",
        "evidence": "URL",
    },
    {
        "url": "https://arxiv.org/abs/2303.04671",
        "text_content": (
            "Visual ChatGPT is a system that enables users to interact with ChatGPT by sending and "
            "receiving not only languages but also images, providing complex visual questions or "
            "visual editing instructions, and providing feedback and asking for corrected results. "
            "It incorporates different Visual Foundation Models and is publicly available. Experiments "
            "show that Visual ChatGPT opens the door to investigating the visual roles of ChatGPT with "
            "the help of Visual Foundation Models."
        ),
        "category": "Academic",
        "evidence": "Text content",
    },
    {
        "url": "https://ab.politiaromana.ro/",
        "text_content": "There is no content available for this text.",
        "category": "None",
        "evidence": "None",
    },
]


def _fetch_text_content_from_url(url: str) -> str:
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
            return soup.get_text()[:2000]
        else:
            print(
                f"Get url failed with status code {response.status_code}.\n"
                f"URL: {url}\nResponse: {response.text[:100]}"
            )
            return "No available content"
    except Exception as e:
        print(f"Get url failed with error: {e}")
        return "No available content"


def _format_examples() -> str:
    parts = []
    for ex in _EXAMPLES:
        parts.append(
            f'URL: {ex["url"]}\n'
            f'Text content: {ex["text_content"]}\n'
            f"OUTPUT:\n"
            f'{{"category": "{ex["category"]}", "evidence": "{ex["evidence"]}"}}\n'
        )
    return "\n".join(parts)


@dataclass
class SummarizedPage:
    url: str
    summary: str


class FetchAndSummarizeExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="SummarizeAgent",
            instructions=_SUMMARIZE_SYSTEM_PROMPT,
        )

    @handler
    async def process(self, url: str, ctx: WorkflowContext[SummarizedPage]) -> None:
        text_content = _fetch_text_content_from_url(url)
        response = await self._agent.run(
            f"Text: {text_content}\nSummary:",
            options=OpenAIChatOptions(temperature=0.2, max_tokens=128),
        )
        await ctx.send_message(SummarizedPage(url=url, summary=response.text))


class ClassifyExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="ClassifyAgent",
            instructions=_CLASSIFY_SYSTEM_PROMPT,
        )

    @handler
    async def classify(self, page: SummarizedPage, ctx: WorkflowContext[Never, dict]) -> None:
        examples_text = _format_examples()
        prompt = (
            f'The selection range of the value of "category" must be within '
            f'"Movie", "App", "Academic", "Channel", "Profile", "PDF" and "None".\n'
            f'The selection range of the value of "evidence" must be within '
            f'"Url", "Text content", and "Both".\n'
            f"Here are a few examples:\n{examples_text}\n"
            f"For a given URL and text content, classify the url to complete the "
            f"category and indicate evidence:\n"
            f"URL: {page.url}\n"
            f"Text content: {page.summary}.\nOUTPUT:"
        )
        response = await self._agent.run(
            prompt,
            options=OpenAIChatOptions(temperature=0.2, max_tokens=128),
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            result = json.loads(text)
        except Exception:
            result = {"category": "None", "evidence": "None"}
        await ctx.yield_output(result)


_fetch_summarize = FetchAndSummarizeExecutor(id="fetch_and_summarize")
_classify = ClassifyExecutor(id="classify")

workflow = (
    WorkflowBuilder(name="FlowWithSymlinksWorkflow", start_executor=_fetch_summarize)
    .add_edge(_fetch_summarize, _classify)
    .build()
)


async def main():
    url = "https://play.google.com/store/apps/details?id=com.twitter.android"
    result = await workflow.run(url)
    output = result.get_outputs()[0]
    print(f"Category: {output.get('category')}")
    print(f"Evidence: {output.get('evidence')}")


if __name__ == "__main__":
    asyncio.run(main())

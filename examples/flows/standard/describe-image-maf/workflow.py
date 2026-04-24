import asyncio
import io
import os
import re
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from PIL import Image as PIL_Image
from typing_extensions import Never

from agent_framework import (
    Agent,
    Content,
    Executor,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)
from agent_framework.openai import OpenAIChatClient

load_dotenv()

_IMAGE_KEY_RE = re.compile(r"^data:image/[^;]+;url$")
_IMAGE_STR_RE = re.compile(r"^data:image/[^;]+;url:\s*(.+)$")

_SYSTEM_PROMPT = """\
As an AI assistant, your task involves interpreting images and responding to questions about the image.
Remember to provide accurate answers based on the information present in the image."""


def _extract_image_url(input_image) -> str:
    if isinstance(input_image, dict):
        for key, url in input_image.items():
            if _IMAGE_KEY_RE.match(key):
                return url
    elif isinstance(input_image, str):
        m = _IMAGE_STR_RE.match(input_image)
        if m:
            return m.group(1).strip()
        return input_image
    return str(input_image)


def _flip_image(image_url: str) -> bytes:
    response = requests.get(image_url)
    image_stream = io.BytesIO(response.content)
    pil_image = PIL_Image.open(image_stream)
    flipped_image = pil_image.transpose(PIL_Image.FLIP_LEFT_RIGHT)
    buffer = io.BytesIO()
    flipped_image.save(buffer, format="PNG")
    return buffer.getvalue()


@dataclass
class ImageInput:
    question: str
    input_image: object  # str URL or dict {"data:image/png;url": "..."}


class FlipAndQuestionExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        client = OpenAIChatClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
        self._agent = Agent(
            client=client,
            name="ImageAgent",
            instructions=_SYSTEM_PROMPT,
        )

    @handler
    async def process(self, image_input: ImageInput, ctx: WorkflowContext[Never, dict]) -> None:
        image_url = _extract_image_url(image_input.input_image)

        # Flip the image
        flipped_bytes = _flip_image(image_url)

        # Build multimodal message with flipped image + question
        image_content = Content.from_data(data=flipped_bytes, media_type="image/png")
        message = Message("user", [image_content, image_input.question])

        response = await self._agent.run(message)
        await ctx.yield_output({
            "answer": response.text,
            "output_image": "(flipped image bytes)",
        })


_executor = FlipAndQuestionExecutor(id="flip_and_question")

workflow = (
    WorkflowBuilder(name="DescribeImageWorkflow", start_executor=_executor)
    .build()
)


async def main():
    result = await workflow.run(
        ImageInput(
            question="How many colors are there in the image?",
            input_image={"data:image/png;url": "https://developer.microsoft.com/_devcom/images/logo-ms-social.png"},
        )
    )
    output = result.get_outputs()[0]
    print(f"Answer: {output['answer']}")


if __name__ == "__main__":
    asyncio.run(main())

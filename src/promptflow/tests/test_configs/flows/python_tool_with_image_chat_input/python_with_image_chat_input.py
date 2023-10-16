from jinja2 import Template
from pathlib import Path

from promptflow.contracts.multimedia import ChatInputList, Image
from promptflow import tool


@tool
def python_with_image_chat_input(chat_history: list, question: ChatInputList, image: Image) -> str:
    template_path = Path(__file__).parent / "chat_tpl.jinja2"
    with open(template_path) as fin:
        template = fin.read()
    prompt = Template(
        template, trim_blocks=True, keep_trailing_newline=True
    ).render(chat_history=chat_history, question=question, image=image)
    return {"prompt": prompt, "image": image}

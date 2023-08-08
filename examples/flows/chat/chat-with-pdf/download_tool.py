# flake8: noqa: E402
import os
import sys

sys.path.append(f"{os.path.dirname(__file__)}/chat_with_pdf")

from promptflow import tool
from chat_with_pdf.download import download


@tool
def download_tool(url: str, env_ready_signal: str) -> str:
    return download(url)

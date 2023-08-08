# flake8: noqa: E402
import os
import sys

sys.path.append(f"{os.path.dirname(__file__)}/chat_with_pdf")

from promptflow import tool
from chat_with_pdf.build_index import create_faiss_index


@tool
def build_index_tool(pdf_path: str) -> str:
    return create_faiss_index(pdf_path)

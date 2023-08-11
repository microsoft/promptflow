# flake8: noqa: E402
import os
import sys

from promptflow import tool

# append chat_with_pdf to sys.path so code inside it can discover its modules
sys.path.append(f"{os.path.dirname(__file__)}/chat_with_pdf")
from chat_with_pdf.build_index import create_faiss_index


@tool
def build_index_tool(pdf_path: str) -> str:
    return create_faiss_index(pdf_path)

from promptflow import tool
from chat_with_pdf.build_index import create_faiss_index


@tool
def build_index_tool(pdf_path: str) -> str:
    return create_faiss_index(pdf_path)

# flake8: noqa: E402
import os
import sys

from promptflow import tool
from promptflow.connections import CustomConnection

# append chat_with_pdf to sys.path so code inside it can discover its modules
sys.path.append(f"{os.path.dirname(__file__)}/chat_with_pdf")
from chat_with_pdf.utils.lock import acquire_lock


@tool
def setup_env(conn: CustomConnection):
    if not conn:
        return
    for key in conn:
        os.environ[key] = conn[key]

    with acquire_lock("create_folder.lock"):
        if not os.path.exists(".pdfs"):
            os.mkdir(".pdfs")
        if not os.path.exists(".index/.pdfs"):
            os.makedirs(".index/.pdfs")

    return "Ready"

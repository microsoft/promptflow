import os

from promptflow import tool
from promptflow.connections import CustomConnection

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

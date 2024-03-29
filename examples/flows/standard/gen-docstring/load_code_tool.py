from promptflow.core import tool
from file import File


@tool
def load_code(source: str):
    file = File(source)
    return file.content

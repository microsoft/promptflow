from promptflow import tool
from file import File


@tool
def load_code(code_path: str):
    file = File(code_path)
    return file.content
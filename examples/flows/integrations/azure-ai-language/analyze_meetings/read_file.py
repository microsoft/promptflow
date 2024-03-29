from promptflow.core import tool


@tool
def read_file(file_path: str) -> str:
    """
    This tool opens a file and reads its contents into a string.

    :param file_path: the file path of the file to be read.
    """

    with open(file_path, 'r', encoding="utf8") as f:
        file = f.read()
    return file

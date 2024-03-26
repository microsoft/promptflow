from promptflow import tool


@tool
def peek_text(text: str, length: int) -> str:
    """
    This tool "peeks" at the first `length` chars of input `text`.
    This is useful for skills that limit input length,
    such as Language Detection.

    :param text: input text.
    :param length: number of chars to peek.
    """

    return text[:length]

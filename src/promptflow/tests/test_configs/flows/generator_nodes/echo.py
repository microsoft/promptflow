from promptflow.core import tool

@tool
def echo(text):
    """yield the input string."""

    echo_text = "Echo - " + text
    for word in echo_text.split():
        yield word
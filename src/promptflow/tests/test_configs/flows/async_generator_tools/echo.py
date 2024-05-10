from promptflow.core import tool

@tool
async def echo(count):
    """yield the input string."""

    echo_text = "Echo - "
    for i in range(count):
        # yield a value to the caller
        yield f"{echo_text}{i}"
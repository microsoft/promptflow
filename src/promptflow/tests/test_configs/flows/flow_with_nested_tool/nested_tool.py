from promptflow import tool


@tool
def echo(input: str, recursive_call=True) -> str:
    if recursive_call:
        return echo(input, recursive_call=False)
    return input

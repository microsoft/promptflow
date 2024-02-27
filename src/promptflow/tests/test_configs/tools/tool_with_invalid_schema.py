from promptflow._core.tool import tool


@tool(name=1, description=1)
def invalid_schema_type(input1: str) -> str:
    return 'hello ' + input1

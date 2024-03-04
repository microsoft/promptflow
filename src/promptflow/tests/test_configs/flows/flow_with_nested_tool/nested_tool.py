from promptflow import tool


@tool
def echo(input: str, recursive_call=True) -> str:
    if recursive_call:
        return echo(input, recursive_call=False)
    
    from promptflow._core.operation_context import OperationContext

    attrs = OperationContext.get_instance()._get_otel_attributes()
    raise Exception(f"{attrs}")

    return input

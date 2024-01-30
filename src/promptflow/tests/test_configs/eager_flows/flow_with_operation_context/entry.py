from promptflow._core.operation_context import OperationContext


def my_flow():
    context = OperationContext.get_instance()
    assert "flow-id" in context
    assert "root-run-id" in context
    return {"flow-id": context["flow-id"], "root-run-id": context["root-run-id"]}

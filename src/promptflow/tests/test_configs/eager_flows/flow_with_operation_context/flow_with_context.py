from promptflow.tracing._operation_context import OperationContext


def my_flow():
    context = OperationContext.get_instance()
    assert "flow_id" in context
    assert "root_run_id" in context
    return {"flow-id": context.flow_id, "root-run-id": context.root_run_id}

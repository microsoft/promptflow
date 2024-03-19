class FlowDoc:
    """A FlexFlow represents an non-dag flow, which uses codes to define the flow.
    FlexFlow basically behave like a Flow, but its entry function should be provided in the flow.dag.yaml file.
    Load of this non-dag flow is provided, but direct call of it will cause exceptions.
    """


class AsyncFlowDoc:
    """Async flow is based on Flow, which is used to invoke flow in async mode.

    Simple Example:

    .. code-block:: python

        from promptflow.core import class AsyncFlow
        flow = AsyncFlow.load(source="path/to/flow.dag.yaml")
        result = await flow(input_a=1, input_b=2)

    """


class FlexFlowDoc:
    """A FlexFlow represents a flow defined with codes directly. It doesn't involve a directed acyclic graph (DAG)
    explicitly, but its entry function haven't been provided.
    FlexFlow basically behave like a Flow.
    Load of this non-dag flow is provided, but direct call of it will cause exceptions.
    """

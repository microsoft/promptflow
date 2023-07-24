import inspect

from promptflow.core.tool import ToolInvoker
from promptflow.core.flow_execution_context import FlowExecutionContext


class DefaultToolInvoker(ToolInvoker):
    def invoke_tool(self, f, *args, **kwargs):
        cur_flow = FlowExecutionContext.active_instance()
        if cur_flow is None:
            return f(*args, **kwargs)  # Do nothing if not in a flow context
        signature = inspect.signature(f)
        argnames = [arg for arg in signature.parameters]
        # Try resolve the variable name of prompt parameter.
        return cur_flow.invoke_tool_with_cache(f, argnames, args, kwargs)

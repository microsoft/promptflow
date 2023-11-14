# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import inspect

from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.tool import ToolInvoker


class DefaultToolInvoker(ToolInvoker):
    def invoke_tool(self, f, *args, **kwargs):
        return f(*args, **kwargs)  # Do nothing

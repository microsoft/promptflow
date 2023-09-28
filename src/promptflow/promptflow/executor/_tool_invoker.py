# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import base64
import inspect
import os

from promptflow._core.flow_execution_context import FlowExecutionContext
from promptflow._core.tool import ToolInvoker


class RecordingEnv:
    PF_RECORDING_MODE = os.environ.get("PF_RECORDING_MODE")
    PF_REPLAY_TIMEOUT_MODE = os.environ.get("PF_REPLAY_TIMEOUT_MODE")
    PF_RECORDING_REGEX = os.environ.get("PF_RECORDING_REGEX")


class DefaultToolInvoker(ToolInvoker):
    def invoke_tool(self, f, *args, **kwargs):
        cur_flow = FlowExecutionContext.active_instance()
        if cur_flow is None:
            return f(*args, **kwargs)  # Do nothing if not in a flow context
        signature = inspect.signature(f)
        argnames = [arg for arg in signature.parameters]
        # Try resolve the variable name of prompt parameter.
        return cur_flow.invoke_tool_with_cache(f, argnames, args, kwargs)


class ToolInvokerWithRecordExtension(DefaultToolInvoker):
    def __init__(self, *args, **kwargs):
        # Read the following environment variables: PF_RECORDING_MODE PF_REPLAY_TIMEOUT_MODE PF_RECORDING_REGEX
        self._record = {}
        self.timeRecord = []

        super().__init__(*args, **kwargs)

    def invoke_tool(self, f, *args, **kwargs):
        super().invoke_tool(f, *args, **kwargs)
        method_and_input_hash = self._get_method_and_input_hash(f, *args, **kwargs)
        self._record.method_and_input_hash = method_and_input_hash

    def _record_call(self, *args, **kwargs):
        self._record.append((args, kwargs))

    def _get_method_and_input_hash(self, f, *args, **kwargs):
        method_name = f.__name__
        sort_kwargs = sorted(kwargs.items())
        input_hash = hash((method_name, args, tuple(sort_kwargs)))
        return input_hash

    def _base64_output(self, output):
        return base64.b64encode(output).decode("utf-8")

    def __getattr__(self, name):
        if name.startswith("_"):
            return super().__getattr__(name)
        else:
            return lambda *args, **kwargs: self._record_call(name, *args, **kwargs)

    def get_record(self):
        return self._record

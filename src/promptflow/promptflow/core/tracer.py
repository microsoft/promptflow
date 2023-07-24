import inspect
import logging
import json
import sys
from contextvars import ContextVar
from datetime import datetime
from typing import Optional

from promptflow.contracts.trace import Trace, TraceType
from promptflow.contracts.tool import ConnectionType
from promptflow.utils.dataclass_serializer import serialize

from .thread_local_singleton import ThreadLocalSingleton


class Tracer(ThreadLocalSingleton):
    CONTEXT_VAR_NAME = "Tracer"
    context_var = ContextVar(CONTEXT_VAR_NAME, default=None)

    def __init__(self, run_id):
        self._run_id = run_id
        self._traces = []
        self._trace_stack = []

    @classmethod
    def start_tracing(cls, run_id):
        tracer = cls(run_id)
        tracer._activate_in_context()

    @classmethod
    def end_tracing(cls, raise_ex=False):
        tracer = cls.active_instance()
        if not tracer:
            msg = "Try end tracing but no active tracer in current context."
            if raise_ex:
                raise Exception(msg)
            logging.warning(msg)
            return []
        tracer._deactivate_in_context()
        return tracer.to_json()

    @classmethod
    def push_tool(cls, f, args, kwargs):
        obj = cls.active_instance()
        sig = inspect.signature(f).parameters
        all_kwargs = {**{k: v for k, v in zip(sig.keys(), args)}, **kwargs}
        all_kwargs = {
            k: ConnectionType.serialize_conn(v) if ConnectionType.is_connection_value(v) else v
            for k, v in all_kwargs.items()
        }
        # TODO: put parameters in self to inputs for builtin tools
        all_kwargs.pop("self", None)
        trace = Trace(
            name=f.__qualname__,
            type=TraceType.TOOL,
            start_time=datetime.utcnow().timestamp(),
            inputs=all_kwargs,
        )
        obj._push(trace)

    @classmethod
    def push(cls, trace: Trace):
        obj = cls.active_instance()
        if not obj:
            logging.warning("Try to push trace but no active tracer in current context.")
            return
        obj._push(trace)

    @staticmethod
    def to_serializable(obj):
        if isinstance(obj, dict) and all(isinstance(k, str) for k in obj.keys()):
            return {k: Tracer.to_serializable(v) for k, v in obj.items()}
        try:
            obj = serialize(obj)
            json.dumps(obj)
        except Exception as e:
            print(f"Fail to serialize object {obj}, error {e}", file=sys.stderr)
            obj = str(obj)
        return obj

    def _push(self, trace: Trace):
        if trace.inputs:
            trace.inputs = self.to_serializable(trace.inputs)
        if not trace.start_time:
            trace.start_time = datetime.utcnow().timestamp()
        if not self._trace_stack:
            self._traces.append(trace)
        else:
            self._trace_stack[-1].children = self._trace_stack[-1].children or []
            self._trace_stack[-1].children.append(trace)
        self._trace_stack.append(trace)

    @classmethod
    def pop(cls, output=None, error: Optional[Exception] = None):
        obj = cls.active_instance()
        obj._pop(output, error)

    def _pop(self, output=None, error: Optional[Exception] = None):
        last_trace = self._trace_stack[-1]
        if output is not None:
            last_trace.output = self.to_serializable(output)
        if error is not None:
            last_trace.error = self._format_error(error)
        self._trace_stack[-1].end_time = datetime.utcnow().timestamp()
        self._trace_stack.pop()

    def to_json(self) -> list:
        return serialize(self._traces)

    @staticmethod
    def _format_error(error: Exception) -> dict:
        return {
            "message": str(error),
            "type": type(error).__qualname__,
        }

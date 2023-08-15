# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Dict, List, Optional, Union

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish, LLMResult

from promptflow._core.tracer import Trace, Tracer, TraceType


class PromptFlowHandler(BaseCallbackHandler):
    def __init__(self):
        super().__init__()
        self._tracer = Tracer.active_instance()

    @property
    def always_verbose(self) -> bool:
        return True

    def _push(self, trace: Trace):
        if not self._tracer:
            return
        self._tracer._push(trace)

    def _pop(self, output=None, error: Optional[Exception] = None):
        if not self._tracer:
            return
        self._tracer._pop(output, error)

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> Any:
        name = self._get_name(serialized) or "LLM"
        trace = Trace(name, TraceType.LANGCHAIN, {"prompts": prompts})
        self._push(trace)

    def on_llm_new_token(self, token: str, **kwargs: Any) -> Any:
        pass  # Wo do not handle this event

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> Any:
        output = response
        self._pop(output)

    def on_llm_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> Any:
        self._pop(error=error)

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> Any:
        name = self._get_name(serialized) or "Chain"
        trace = Trace(name, TraceType.LANGCHAIN, inputs)
        self._push(trace)

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> Any:
        self._pop(outputs)

    def on_chain_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> Any:
        self._pop(error=error)

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> Any:
        name = self._get_name(serialized) or "Tool"
        trace = Trace(name, TraceType.LANGCHAIN, {"input_str": input_str})
        self._push(trace)

    def on_tool_end(self, output: str, **kwargs: Any) -> Any:
        self._pop(output)

    def on_tool_error(
        self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any
    ) -> Any:
        self._pop(error=error)

    def on_text(self, text: str, **kwargs: Any) -> Any:
        pass

    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any:
        name = action.tool
        trace = Trace(name, TraceType.LANGCHAIN, {"tool_input": action.tool_input})
        self._push(trace)

    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> Any:
        output = finish.return_values
        self._pop(output)

    def _get_name(self, serialized: Dict[str, Any]):
        # For version 0.0.197 and earlier, the name is stored in the "name" field,
        # and for later versions, the name is stored in the "id" field.
        # If none exists, return None and use a default name.
        if "name" in serialized.keys():
            return serialized["name"]
        elif "id" in serialized.keys() and isinstance(serialized["id"], list):
            return serialized["id"][-1]
        else:
            return None


def get_langchain_callback_manager():
    # To ensure backward compatibility, use CallbackManager for version 0.0.153 and earlier,
    # and use BaseCallbackManager for later versions.
    try:
        from langchain.callbacks.base import CallbackManager

        return CallbackManager([PromptFlowHandler()])
    except ImportError:
        from langchain.callbacks.base import BaseCallbackManager

        return BaseCallbackManager([PromptFlowHandler()])

# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Dict, List, Optional, Union

from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import AgentAction, AgentFinish, LLMResult

from promptflow._core.tracer import Trace, Tracer, TraceType


class PromptFlowCallbackHandler(BaseCallbackHandler):
    """`PromptFlowCallbackHandler` implements the `BaseCallbackHandler` interface,
    which has a method for each event that can be subscribed to.
    The appropriate method will be called on the handler when the event is triggered."""

    def __init__(self):
        super().__init__()
        self._tracer = Tracer.active_instance()

    @property
    def always_verbose(self) -> bool:
        """Whether to always be verbose."""

        return True

    def _push(self, trace: Trace):
        if not self._tracer:
            return
        self._tracer._push(trace)

    def _pop(self, output=None, error: Optional[Exception] = None):
        if not self._tracer:
            return
        self._tracer._pop(output, error)

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        """Run when LLM starts running.

        :param serialized: The serialized LLM object.
        :type serialized: Dict[str, Any]
        :param prompts: The prompts used to run LLM.
        :type prompts: List[str]
        """

        name = self._get_name(serialized) or "LLM"
        trace = Trace(name, TraceType.LANGCHAIN, {"prompts": prompts})
        self._push(trace)

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Run on new LLM token. Only available when streaming is enabled.

        :param token: The new token.
        :type token: str
        """

        pass  # Wo do not handle this event

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Run when LLM ends running.

        :param response: The response from LLM.
        :type response: LLMResult
        """

        output = response
        self._pop(output)

    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> None:
        """Run when LLM errors.

        :param error: The error from LLM.
        :type error: Union[Exception, KeyboardInterrupt]
        """

        self._pop(error=error)

    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> None:
        """Run when chain starts running.

        :param serialized: The serialized chain object.
        :type serialized: Dict[str, Any]
        :param inputs: The inputs used to run chain.
        :type inputs: Dict[str, Any]
        """

        name = self._get_name(serialized) or "Chain"
        trace = Trace(name, TraceType.LANGCHAIN, inputs)
        self._push(trace)

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Run when chain ends running.

        :param outputs: The outputs from chain.
        :type outputs: Dict[str, Any]
        """

        self._pop(outputs)

    def on_chain_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> None:
        """Run when chain errors.

        :param error: The error from chain.
        :type error: Union[Exception, KeyboardInterrupt]
        """

        self._pop(error=error)

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> None:
        """Run when tool starts running.

        :param serialized: The serialized tool object.
        :type serialized: Dict[str, Any]
        :param input_str: The input string used to run tool.
        :type input_str: str
        """

        name = self._get_name(serialized) or "Tool"
        trace = Trace(name, TraceType.LANGCHAIN, {"input_str": input_str})
        self._push(trace)

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Run when tool ends running.

        :param output: The output from tool.
        :type output: str
        """

        self._pop(output)

    def on_tool_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> None:
        """Run when tool errors.

        :param error: The error from tool.
        :type error: Union[Exception, KeyboardInterrupt]
        """

        self._pop(error=error)

    def on_text(self, text: str, **kwargs: Any) -> None:
        """Run on arbitrary text.

        :param text: The text.
        :type text: str
        """

        pass

    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> None:
        """Run on agent action.

        :param action: The action from agent.
        :type action: AgentAction
        """

        name = action.tool
        trace = Trace(name, TraceType.LANGCHAIN, {"tool_input": action.tool_input})
        self._push(trace)

    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> None:
        """Run on agent end.

        :param finish: The finish from agent.
        :type finish: AgentFinish
        """

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

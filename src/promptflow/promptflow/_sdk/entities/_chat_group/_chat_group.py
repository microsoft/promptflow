# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import Any, Dict, List

from promptflow._sdk._constants import ChatGroupSpeakOrder
from promptflow._sdk._errors import ChatGroupError
from promptflow._sdk.entities._chat_group._chat_agent import ChatAgent

# from promptflow._sdk.entities._chat_group._chat_group_io import ChatAgentOutputs
from promptflow._utils.logger_utils import get_cli_sdk_logger

logger = get_cli_sdk_logger()


class ChatGroup:
    """Chat group entity"""

    def __init__(
        self,
        agents: List[ChatAgent] = None,
        entry_agent: ChatAgent = None,
        speak_order: ChatGroupSpeakOrder = ChatGroupSpeakOrder.SEQUENTIAL,
        max_turns: int = None,
        max_tokens: int = None,
        max_time: int = None,
        inputs: Dict[str, Dict[str, Any]] = None,
        outputs: Dict[str, Dict[str, Any]] = None,
    ):
        self._agents = agents
        self._entry_agent = entry_agent
        self._agents_dict, self._speak_order_list = self._prepare_agents(agents, entry_agent, speak_order)
        self._max_turns, self._max_tokens, self._max_time = self._validate_int_parameters(
            max_turns, max_tokens, max_time
        )
        self.inputs, self.outputs = self._prepare_io(inputs, outputs)
        self.chat_history = []

    def _prepare_agents(self, agents, entry_agent, speak_order):
        """Prepare agents"""
        # check agents is a non-empty list of ChatAgent
        if (
            not isinstance(agents, list)
            or len(agents) == 0
            or not all(isinstance(agent, ChatAgent) for agent in agents)
        ):
            raise ChatGroupError(f"Agents should be a non-empty list of ChatAgent. Got {agents!r} instead.")

        # check entry_agent is in agents
        if entry_agent is not None and entry_agent not in agents:
            raise ChatGroupError(f"Entry agent {entry_agent.name} is not in agents list.")

        speak_order_list = self._calculate_speak_order(agents, entry_agent, speak_order)
        agents_dict = {agent.name: agent for agent in agents}
        return agents_dict, speak_order_list

    def _calculate_speak_order(self, agents, entry_agent, speak_order) -> List[str]:
        """Calculate speak order"""
        if speak_order == ChatGroupSpeakOrder.SEQUENTIAL:
            if entry_agent:
                logger.warn(
                    f"Entry agent {entry_agent.name!r} is ignored when speak order is sequential. "
                    f"The first agent in the list will be the entry agent: {agents[0].name!r}."
                )
            return [agent.name for agent in agents]
        else:
            raise NotImplementedError(f"Speak order {speak_order} is not supported yet.")

    def _prepare_io(self, inputs: Dict[str, Dict[str, Any]], outputs: Dict[str, Dict[str, Any]]):
        """Prepare inputs and outputs"""
        if not isinstance(inputs, dict):
            raise ChatGroupError(f"Inputs should be a dictionary. Got {type(inputs)!r} instead.")
        if not isinstance(outputs, dict):
            raise ChatGroupError(f"Outputs should be a dictionary. Got {type(outputs)!r} instead.")

        # add referenced name for chat group inputs
        for key in inputs:
            inputs[key]["referenced_name"] = f"${{chat_group.inputs.{key}}}"

        # refine outputs reference and add referenced name for chat group outputs
        for key in outputs:
            # refine outputs reference
            reference = outputs[key].get("reference")
            if not reference:
                raise ChatGroupError(f"Output {key!r} should have a reference. Got {reference!r} instead.")
            if isinstance(reference, dict):
                outputs[key]["reference"] = reference["referenced_name"]
            elif isinstance(reference, str):
                if not reference.startswith("${"):
                    raise ChatGroupError(
                        f"Output {key!r} reference should start with '${{'. Got {reference!r} instead."
                    )

            # add referenced name for chat group outputs
            outputs[key]["referenced_name"] = f"${{chat_group.outputs.{key}}}"

        return inputs, outputs

    def _validate_int_parameters(self, max_turns, max_tokens, max_time):
        """Validate int parameters"""
        if max_turns is not None and not isinstance(max_turns, int):
            raise ChatGroupError(f"max_turns should be an integer. Got {type(max_turns)!r} instead.")
        if max_tokens is not None and not isinstance(max_tokens, int):
            raise ChatGroupError(f"max_tokens should be an integer. Got {type(max_tokens)!r} instead.")
        if max_time is not None and not isinstance(max_time, int):
            raise ChatGroupError(f"max_time should be an integer. Got {type(max_time)!r} instead.")

        return max_turns, max_tokens, max_time

    def invoke(self, *args, **kwargs):
        """Invoke the chat group"""
        # ensure inputs are provided
        self._process_execution_parameters(**kwargs)

    def _process_execution_parameters(self, **kwargs) -> None:
        """Process execution parameters"""
        for key in self.inputs:
            group_input = self.inputs[key]
            if key in kwargs:
                value = kwargs.get(key)
                if not isinstance(value, group_input["type"]):
                    raise ChatGroupError(
                        f"Input {key!r} should be of type {input['type']!r}. Got {type(value)!r} instead."
                    )
                self.inputs[key]["value"] = value
            elif "default" in group_input:
                self.inputs[key]["value"] = group_input["default"]

        for key in self.inputs:
            if "value" not in self.inputs[key]:
                raise ChatGroupError(f"Chat group input {key!r} is missing actual value.")

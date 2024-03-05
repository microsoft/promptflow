# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import time
from itertools import cycle
from typing import Any, Dict, List, Union

from promptflow._sdk._constants import CHAT_GROUP_NAME, ChatGroupSpeakOrder
from promptflow._sdk._errors import ChatGroupError
from promptflow._sdk._utils import parse_chat_group_data_binding
from promptflow._sdk.entities._chat_group._chat_agent import ChatAgent
from promptflow._sdk.entities._chat_group._chat_group_io import ChatGroupInputs, ChatGroupOutputs

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
        self._speak_order = speak_order
        self._agents_dict, self._speak_order_list = self._prepare_agents(agents, entry_agent, speak_order)
        self._max_turns, self._max_tokens, self._max_time = self._validate_int_parameters(
            max_turns, max_tokens, max_time
        )
        self.inputs, self.outputs = self._prepare_io(inputs, outputs)
        self.chat_history = ChatGroupHistory(self)

    def _prepare_agents(self, agents: List[ChatAgent], entry_agent: ChatAgent, speak_order: ChatGroupSpeakOrder):
        """Prepare agents"""
        logger.info("Preparing agents in chat group.")
        # check agents is a non-empty list of ChatAgent
        if (
            not isinstance(agents, list)
            or len(agents) == 0
            or not all(isinstance(agent, ChatAgent) for agent in agents)
        ):
            raise ChatGroupError(f"Agents should be a non-empty list of ChatAgent. Got {agents!r} instead.")

        # check entry_agent is in agents
        if entry_agent is not None and entry_agent not in agents:
            raise ChatGroupError(f"Entry agent {entry_agent.name} is not in agents list {agents}.")

        speak_order_list = self._calculate_speak_order(agents, entry_agent, speak_order)
        agents_dict = {agent.name: agent for agent in agents}
        return agents_dict, cycle(speak_order_list)

    def _calculate_speak_order(
        self, agents: List[ChatAgent], entry_agent: ChatAgent, speak_order: ChatGroupSpeakOrder
    ) -> List[str]:
        """Calculate speak order"""
        logger.info(f"Calculating agents speak order for chat group with specified speak order {speak_order.value!r}.")
        if speak_order == ChatGroupSpeakOrder.SEQUENTIAL:
            if entry_agent:
                logger.warn(
                    f"Entry agent {entry_agent.name!r} is ignored when speak order is sequential. "
                    f"The first agent in the list will be the entry agent: {agents[0].name!r}."
                )
            speak_order_list = [agent.name for agent in agents]
            logger.info(f"Calculated agent speak order is {speak_order_list!r}.")
            return speak_order_list
        else:
            raise NotImplementedError(f"Speak order {speak_order.value} is not supported yet.")

    def _prepare_io(self, inputs: Dict[str, Dict[str, Any]], outputs: Dict[str, Dict[str, Any]]):
        """Prepare inputs and outputs"""
        logger.info("Preparing chat group inputs and outputs.")
        if not isinstance(inputs, dict):
            raise ChatGroupError(f"Inputs should be a dictionary. Got {type(inputs)!r} instead.")
        if not isinstance(outputs, dict):
            raise ChatGroupError(f"Outputs should be a dictionary. Got {type(outputs)!r} instead.")

        # add referenced name for chat group inputs
        for key in inputs:
            inputs[key]["referenced_name"] = f"${{{CHAT_GROUP_NAME}.inputs.{key}}}"
            # TODO: Remove "initialize for" and implement a more elegant way to handle it
            # initialize_for is a temporary solution to provide the first reference for agent's input. In the scenario
            # that a agent's input is bound with another agent's output but that agent has not run yet and we hope
            # the first round input can be provided by chat group inputs, we can use "initialize_for" to do the trick.
            if "initialize_for" in inputs[key]:
                value = inputs[key]["initialize_for"]
                if isinstance(value, str):
                    agent_name, io_type, io_name = parse_chat_group_data_binding(value)
                    agent_input = getattr(self._agents_dict[agent_name], io_type)[io_name]
                    agent_input["first_reference"] = f"${{{CHAT_GROUP_NAME}.inputs.{key}}}"
                elif isinstance(value, dict):
                    value["first_reference"] = f"${{{CHAT_GROUP_NAME}.inputs.{key}}}"
        logger.debug(f"Chat group inputs: {inputs!r}")

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
            outputs[key]["referenced_name"] = f"${{{CHAT_GROUP_NAME}.outputs.{key}}}"
        logger.debug(f"Chat group outputs: {outputs!r}")

        return ChatGroupInputs(inputs), ChatGroupOutputs(outputs)

    def _validate_int_parameters(self, max_turns: int, max_tokens: int, max_time: int):
        """Validate int parameters"""
        logger.debug("Validating integer parameters for chat group.")
        if max_turns is not None and not isinstance(max_turns, int):
            raise ChatGroupError(f"max_turns should be an integer. Got {type(max_turns)!r} instead.")
        if max_tokens is not None and not isinstance(max_tokens, int):
            raise ChatGroupError(f"max_tokens should be an integer. Got {type(max_tokens)!r} instead.")
        if max_time is not None and not isinstance(max_time, int):
            raise ChatGroupError(f"max_time should be an integer. Got {type(max_time)!r} instead.")

        logger.info(
            f"Chat group maximum turns: {max_turns!r}, maximum tokens: {max_tokens!r}, maximum time: {max_time!r}."
        )
        return max_turns, max_tokens, max_time

    def invoke(self, *args, **kwargs):
        """Invoke the chat group"""
        if args:
            raise ChatGroupError(f"Chat group invoke does not accept positional arguments. Got {args!r} instead.")

        logger.info("Invoking chat group.")
        # ensure inputs are provided
        self._process_execution_parameters(**kwargs)

        chat_round = 0
        chat_token = 0
        chat_start_time = time.time()
        while True:
            chat_round += 1

            # select current agent and run
            current_agent = self._select_agent()
            logger.info(f"[Round {chat_round}] Chat agent {current_agent.name!r} is speaking.")
            agent_input_values = self._get_agent_input_values(current_agent)
            result = current_agent.invoke(**agent_input_values)

            # post process after agent's invocation
            self._update_information_with_result(current_agent, result)
            # TODO: Get used token from result and update chat_token

            # check if the chat group should continue
            continue_chat = self._check_continue_condition(chat_round, chat_token, chat_start_time)
            if not continue_chat:
                logger.info(
                    f"Chat group stops at round {chat_round!r}, token cost {chat_token!r}, "
                    f"time cost {time.time() - chat_start_time} seconds."
                )
                break

    def _process_execution_parameters(self, **kwargs) -> None:
        """Process execution parameters"""
        # enrich the actual value for chat group inputs
        logger.info(f"Processing execution parameters for chat group with inputs {kwargs!r}.")
        for key in self.inputs:
            group_input = self.inputs[key]
            if key in kwargs:
                value = kwargs.get(key)
                if not isinstance(value, group_input["type"]):
                    raise ChatGroupError(
                        f"Input {key!r} should be of type {group_input['type']!r}. Got {type(value)!r} instead."
                    )
                group_input["value"] = value
            elif "default" in group_input:
                group_input["value"] = group_input["default"]
        logger.debug(f"Chat group inputs with enriched actual values: {self.inputs!r}")

        # check if all inputs have actual values
        missed_inputs = []
        for key in self.inputs:
            if "value" not in self.inputs[key]:
                missed_inputs.append(key)
        if missed_inputs:
            raise ChatGroupError(f"Chat group inputs are not provided: {missed_inputs}.")

        # update chat history with initial group level inputs
        contents = {key: self.inputs[key]["value"] for key in self.inputs}
        self.chat_history._update_history(self, contents)

        # check for ignored inputs
        ignored_keys = set(kwargs.keys()) - set(self.inputs.keys())
        if ignored_keys:
            logger.warning(
                f"Ignoring inputs {ignored_keys!r} for the chat group, " f"expected one of {list(self.inputs.keys())}."
            )

    def _select_agent(self) -> ChatAgent:
        """Select next agent"""
        if self._speak_order == ChatGroupSpeakOrder.LLM:
            return self._predict_next_agent_with_llm()
        next_agent_name = next(self._speak_order_list)
        return self._agents_dict[next_agent_name]

    def _get_agent_input_values(self, agent: ChatAgent) -> Dict[str, Any]:
        """Get agent input values"""
        input_values = {}
        for key in agent.inputs:
            agent_input = agent.inputs[key]
            value = None
            # first reference works as the initial value for agent's input, so it should be removed after the first use
            if "first_reference" in agent_input:
                reference = agent_input["first_reference"]
                owner, io_type, io_name = parse_chat_group_data_binding(reference)
                owner = self if owner == CHAT_GROUP_NAME else self._agents_dict[owner]
                value = getattr(owner, io_type)[io_name]["value"]
                agent_input.pop("first_reference", None)
            elif "reference" in agent_input:
                reference = agent_input["reference"]
                owner, io_type, io_name = parse_chat_group_data_binding(reference)
                owner = self if owner == CHAT_GROUP_NAME else self._agents_dict[owner]
                value = getattr(owner, io_type)[io_name]["value"]
            elif "value" in agent_input:
                value = agent_input["value"]
            elif "default" in agent_input:
                value = agent_input["default"]
            input_values[key] = value
        logger.debug(f"Input values for agent {agent.name!r}: {input_values!r}")
        return input_values

    def _update_information_with_result(self, agent: ChatAgent, result: dict) -> None:
        """Update information with result"""
        logger.debug(f"Updating chat group information with result from agent {agent.name!r}: {result!r}.")

        # 1. update group chat history
        self.chat_history._update_history(agent, result)

        # 2. Update the agent output value
        for key, value in result.items():
            if key in agent.outputs:
                agent.outputs[key]["value"] = value

    def _check_continue_condition(self, chat_round: int, chat_token: int, chat_start_time: float) -> bool:
        continue_chat = True
        time_cost = time.time() - chat_start_time

        # 1. check if the chat round reaches the maximum
        if self._max_turns is not None and chat_round >= self._max_turns:
            logger.warn(f"Chat round {chat_round!r} reaches the maximum {self._max_turns!r}.")
            continue_chat = False

        # 2. check if the chat token reaches the maximum
        if self._max_tokens is not None and chat_token >= self._max_tokens:
            logger.warn(f"Chat token {chat_token!r} reaches the maximum {self._max_tokens!r}.")
            continue_chat = False

        # 3. check if the chat time reaches the maximum
        if self._max_time is not None and time_cost >= self._max_time:
            logger.warn(f"Chat time reaches the maximum {self._max_time!r} seconds.")
            continue_chat = False

        if continue_chat:
            logger.info(
                f"Chat group continues at round {chat_round!r}, "
                f"token cost {chat_token!r}, time cost {round(time_cost, 2)!r} seconds."
            )
        return continue_chat

    def _predict_next_agent_with_llm(self) -> ChatAgent:
        """Predict next agent for non-deterministic speak order."""
        raise NotImplementedError(f"Speak order {self._speak_order} is not supported yet.")


class ChatGroupHistory:
    """Chat group history entity"""

    def __init__(self, chat_group: ChatGroup):
        self._history = []
        self._chat_group = chat_group

    def _update_history(self, agent: Union[ChatAgent, ChatGroup], result: Any):
        """Update chat history"""
        is_agent = isinstance(agent, ChatAgent)
        speaker = agent.name if is_agent else CHAT_GROUP_NAME
        message = None
        # Normally we assume every agent only has 1 output so we take the first one.
        # For the initial chat group level input, we put all inputs into the history.
        if isinstance(result, dict) and len(result) > 0:
            message = list(result.values())[0] if is_agent else result
        elif isinstance(result, str):
            message = result
        self._history.append((speaker, message))

    @property
    def history(self):
        return self._history

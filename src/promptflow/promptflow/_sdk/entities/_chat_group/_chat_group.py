# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import time
from itertools import cycle
from typing import Any, Dict, List, Optional

from promptflow._sdk._constants import CHAT_GROUP_NAME, STOP_SIGNAL, ChatGroupSpeakOrder
from promptflow._sdk._errors import ChatGroupError
from promptflow._sdk._utils import parse_chat_group_data_binding
from promptflow._sdk.entities._chat_group._chat_group_io import ChatGroupInputs, ChatGroupOutputs
from promptflow._sdk.entities._chat_group._chat_role import ChatRole
from promptflow._utils.logger_utils import get_cli_sdk_logger

logger = get_cli_sdk_logger()


class ChatGroup:
    """Chat group entity, can invoke a multi-turn conversation with multiple chat roles.

    :param roles: List of chat roles in the chat group.
    :type roles: List[ChatRole]
    :param speak_order: Speak order of the chat group. Default to be sequential which is the order of the roles list.
    :type speak_order: ChatGroupSpeakOrder
    :param max_turns: Maximum turns of the chat group. Default to be None which means no limit.
    :type max_turns: Optional[int]
    :param max_tokens: Maximum tokens of the chat group. Default to be None which means no limit.
    :type max_tokens: Optional[int]
    :param max_time: Maximum time of the chat group. Default to be None which means no limit.
    :type max_time: Optional[int]
    :param stop_signal: Stop signal of the chat group. Default to be "[STOP]".
    :type stop_signal: Optional[str]
    :param entry_role: Entry role of the chat group. Default to be None which means the first role in the roles list.
        Only meaningful when speak order is not sequential.
    """

    def __init__(
        self,
        roles: List[ChatRole],
        speak_order: ChatGroupSpeakOrder = ChatGroupSpeakOrder.SEQUENTIAL,
        max_turns: Optional[int] = None,
        max_tokens: Optional[int] = None,
        max_time: Optional[int] = None,
        stop_signal: Optional[str] = STOP_SIGNAL,
        entry_role: Optional[ChatRole] = None,
    ):
        self._roles = roles
        self._speak_order = speak_order
        self._roles_dict, self._speak_order_list = self._prepare_roles(roles, entry_role, speak_order)
        self._max_turns, self._max_tokens, self._max_time = self._validate_int_parameters(
            max_turns, max_tokens, max_time
        )
        self._stop_signal = stop_signal
        self._entry_role = entry_role
        self._conversation_history = []

    @property
    def conversation_history(self):
        return self._conversation_history

    def _prepare_roles(self, roles: List[ChatRole], entry_role: ChatRole, speak_order: ChatGroupSpeakOrder):
        """Prepare roles"""
        logger.info("Preparing roles in chat group.")
        # check roles is a non-empty list of ChatRole
        if not isinstance(roles, list) or len(roles) == 0 or not all(isinstance(role, ChatRole) for role in roles):
            raise ChatGroupError(f"Agents should be a non-empty list of ChatRole. Got {roles!r} instead.")

        # check entry_role is in roles
        if entry_role is not None and entry_role not in roles:
            raise ChatGroupError(f"Entry role {entry_role.name} is not in roles list {roles!r}.")

        speak_order_list = self._get_speak_order(roles, entry_role, speak_order)
        roles_dict = {role.name: role for role in roles}
        return roles_dict, cycle(speak_order_list)

    def _get_speak_order(
        self, roles: List[ChatRole], entry_role: Optional[ChatRole], speak_order: ChatGroupSpeakOrder
    ) -> List[str]:
        """Calculate speak order"""
        if speak_order == ChatGroupSpeakOrder.SEQUENTIAL:
            if entry_role:
                logger.warn(
                    f"Entry role {entry_role.name!r} is ignored when speak order is sequential. "
                    f"The first role in the list will be the entry role: {roles[0].name!r}."
                )

            speak_order_list = [role.name for role in roles]
            logger.info(f"Role speak order is {speak_order_list!r}.")
            return speak_order_list
        else:
            raise NotImplementedError(f"Speak order {speak_order.value!r} is not supported yet.")

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
            # initialize_for is a temporary solution to provide the first reference for role's input. In the scenario
            # that a role's input is bound with another role's output but that role has not run yet and we hope
            # the first round input can be provided by chat group inputs, we can use "initialize_for" to do the trick.
            if "initialize_for" in inputs[key]:
                value = inputs[key]["initialize_for"]
                if isinstance(value, str):
                    role_name, io_type, io_name = parse_chat_group_data_binding(value)
                    role_input = getattr(self._roles_dict[role_name], io_type)[io_name]
                    role_input["first_reference"] = f"${{{CHAT_GROUP_NAME}.inputs.{key}}}"
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

    @staticmethod
    def _validate_int_parameters(max_turns: int, max_tokens: int, max_time: int):
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
        if args or kwargs:
            logger.warn(
                f"Chat group invoke does not accept arguments, got {args!r} and {kwargs!r} instead and ignored them."
            )

        logger.info("Invoking chat group.")

        chat_round = 0
        chat_token = 0
        chat_start_time = time.time()
        while True:
            chat_round += 1

            # select current role and run
            current_role = self._select_role()
            logger.info(f"[Round {chat_round}] Chat role {current_role.name!r} is speaking.")
            role_input_values = self._get_role_input_values(current_role)
            # TODO: Hide flow-invoker and executor log for execution
            result = current_role.invoke(**role_input_values)
            logger.info(f"[Round {chat_round}] Chat role {current_role.name!r} result: {result!r}.")

            # post process after role's invocation
            self._update_information_with_result(current_role, result)
            # TODO: Get used token from result and update chat_token

            # check if the chat group should continue
            continue_chat = self._check_continue_condition(chat_round, chat_token, chat_start_time)
            if not continue_chat:
                logger.info(
                    f"Chat group stops at round {chat_round!r}, token cost {chat_token!r}, "
                    f"time cost {time.time() - chat_start_time} seconds."
                )
                break

    def _select_role(self) -> ChatRole:
        """Select next role"""
        if self._speak_order == ChatGroupSpeakOrder.LLM:
            return self._predict_next_role_with_llm()
        next_role_name = next(self._speak_order_list)
        return self._roles_dict[next_role_name]

    def _get_role_input_values(self, role: ChatRole) -> Dict[str, Any]:
        """Get role input values"""
        input_values = {}
        for key in role.inputs:
            role_input = role.inputs[key]
            value = role_input.get("value", None)
            # only conversation history binding needs to be processed here, other values are specified when
            # initializing the chat role.
            if value == "${parent.conversation_history}":
                value = self._conversation_history
            input_values[key] = value
        logger.debug(f"Input values for role {role.name!r}: {input_values!r}")
        return input_values

    def _update_information_with_result(self, role: ChatRole, result: dict) -> None:
        """Update information with result"""
        logger.debug(f"Updating chat group information with result from role {role.name!r}: {result!r}.")

        # 1. update group chat history
        self._update_conversation_history(role, result)

        # 2. Update the role output value
        for key, value in result.items():
            if key in role.outputs:
                role.outputs[key]["value"] = value

    def _update_conversation_history(self, role: ChatRole, result: dict) -> None:
        """Update conversation history"""
        self._conversation_history.append((role.role, result))

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

    def _predict_next_role_with_llm(self) -> ChatRole:
        """Predict next role for non-deterministic speak order."""
        raise NotImplementedError(f"Speak order {self._speak_order} is not supported yet.")

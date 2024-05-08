# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Any, Dict, List, Mapping, Optional

from promptflow._orchestrator._constants import (
    CHAT_ROLE_KEY,
    CONVERSATION_HISTORY_EXPRESSION,
    CONVERSATION_HISTORY_OUTPUT_KEY,
)
from promptflow._orchestrator._errors import (
    InvalidChatRoleCount,
    InvalidMaxTurnValue,
    MissingConversationHistoryExpression,
    MultipleConversationHistoryInputsMapping,
    UsingReservedRoleKey,
)
from promptflow._proxy._base_executor_proxy import AbstractExecutorProxy
from promptflow._proxy._proxy_factory import ProxyFactory
from promptflow._sdk.entities._chat_group._chat_role import ChatRole
from promptflow._utils.execution_utils import apply_default_value_for_input
from promptflow._utils.logger_utils import bulk_logger
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
from promptflow.contracts.run_info import Status
from promptflow.executor._result import LineResult
from promptflow.storage import AbstractRunStorage


class ChatGroupOrchestrator:
    def __init__(
        self,
        chat_group_roles: List[ChatRole],
        max_turn: Optional[int] = 0,
        storage: Optional[AbstractRunStorage] = None,
        max_lines_count: Optional[int] = None,
        **kwargs,
    ):
        """Chat group orchestrator schedule runs for each line in batch inputs.
        :param chat_group_roles: chat group roles
        :type chat_group_roles: List[ChatRole]
        :param max_turn: max turn of chat, defaults to None
        :type max_turn: Optional[int], optional
        :param storage: storage, defaults to None
        :type storage: Optional[AbstractRunStorage], optional
        :param max_lines_count: max lines from inputs, defaults to None
        :type max_lines_count: Optional[int], optional
        """
        self._storage = storage
        self._max_turn = max_turn
        self._chat_group_roles = chat_group_roles
        self._max_lines_count = max_lines_count

        if self._max_turn == 0:
            bulk_logger.error(f"Invalid max_turn value for chat group run: {self._max_turn}")
            message = f"Invalid max_turn value for chat group run: {self._max_turn}. Please assign max_turn at least 1."
            raise InvalidMaxTurnValue(message=message)

        if len(self._chat_group_roles) < 2:
            bulk_logger.error(f"Invalid chat group role count: {len(self._chat_group_roles)}")
            message = (
                f"Invalid chat group role count: {len(self._chat_group_roles)}. "
                "Please define 2 chat group roles at least."
            )
            raise InvalidChatRoleCount(message=message)

        self._executor_proxies: List[AbstractExecutorProxy] = self._create_executor_proxy(**kwargs)

    @classmethod
    def create(
        cls,
        chat_group_roles: List[ChatRole],
        max_turn: Optional[int] = 0,
        storage: Optional[AbstractRunStorage] = None,
        max_lines_count: Optional[int] = None,
    ) -> "ChatGroupOrchestrator":

        return ChatGroupOrchestrator(chat_group_roles, max_turn, storage, max_lines_count)

    def _create_executor_proxy(self, **kwargs) -> List[AbstractExecutorProxy]:
        """create executor proxy for each chat role according to language
        :return: proxy list
        :rtype: List[AbstractExecutorProxy]
        """
        executor_proxy_list = []
        executor_proxy_factory = ProxyFactory()
        for chat_role in self._chat_group_roles:
            executor_proxy = executor_proxy_factory.create_executor_proxy(
                flow_file=chat_role._flow_file,
                working_dir=chat_role._working_dir,
                connections=chat_role._connections,
                storage=self._storage,
                language=chat_role.check_language_from_yaml(),
                executor_client=chat_role._executor_client,
                environment_variables=chat_role._environment_variables,
                log_path=chat_role._log_path,
                output_dir=chat_role._output_dir,
                worker_count=chat_role._worker_count,
                line_timeout_sec=chat_role._line_timeout_sec,
                init_kwargs=chat_role._init_kwargs,
                **kwargs,
            )
            bulk_logger.info(f"Created executor proxy for role:{chat_role.role}. name: {chat_role._name}")
            executor_proxy_list.append(executor_proxy)
        return executor_proxy_list

    async def destroy(self):
        for executor_proxy in self._executor_proxies:
            await executor_proxy.destroy()

    async def _schedule_line_runs(
        self,
        line_index: int,
        inputs: Mapping[str, Any] = None,
        run_id: str = None,
    ) -> LineResult:
        """schedule runs for each line in batch inputs.
        It also resolve flow inputs and flow outputs for each turn.
        :param line_index: line index in batch inputs
        :type line_index: int
        :param inputs: raw input line of line_index, defaults to None
        :type inputs: Mapping[str, Any], optional
        :param run_id: run id, defaults to None
        :type run_id: str, optional
        :return: line result
        :rtype: LineResult
        """
        outputs: dict = {}
        aggregation_inputs: dict = {}
        current_line_result: LineResult = None

        total_roles = len(self._chat_group_roles)
        conversation_history: List[Mapping[str, Any]] = []
        batch_inputs = self._process_batch_inputs(inputs)
        bulk_logger.info(f"Finish process batch inputs and applying inputs mapping for line number:{line_index}")

        bulk_logger.info(f"Start to schedule runs for run id: {run_id}, line number: {line_index}")

        for turn in range(self._max_turn):
            role_index = turn % total_roles
            executor_proxy = self._executor_proxies[role_index]
            chat_role = self._chat_group_roles[role_index]
            chat_role_input = batch_inputs[role_index]
            conversation_history_key = next(
                (key for key, value in chat_role._inputs_mapping.items() if value == CONVERSATION_HISTORY_EXPRESSION),
                None,
            )
            if conversation_history_key is None:
                bulk_logger.error(
                    f"Cannot find conversation expression mapping for "
                    f"chat role: {chat_role.role}. name: {chat_role._name}"
                )
                message = (
                    f"Cannot find conversation expression mapping for "
                    f"chat role: {chat_role.role}. name: {chat_role._name} "
                    f"Please use define {CONVERSATION_HISTORY_EXPRESSION} for a flow input."
                )
                raise MissingConversationHistoryExpression(message=message)
            chat_role_input[conversation_history_key] = conversation_history
            bulk_logger.info(f"Start to execute turn {turn}. role: {chat_role.role}. name: {chat_role._name}")

            current_line_result = await executor_proxy.exec_line_async(chat_role_input, line_index, run_id)
            self._process_flow_outputs(
                turn, chat_role, current_line_result, conversation_history, outputs, aggregation_inputs
            )
            bulk_logger.info(
                f"Finish process line result for "
                f"line number: {line_index}, turn:{turn}. role:{chat_role.role}, name: {chat_role._name}"
            )

            if (
                current_line_result.run_info.status == Status.Failed
                or current_line_result.run_info.status == Status.Canceled
            ):
                bulk_logger.warning(
                    f"Stop chat since run of turn:{turn} end with status {current_line_result.run_info.status}. "
                    f"line number: {line_index}, role:{chat_role.role}, name: {chat_role._name}"
                )
                break

            if any(value == chat_role._stop_signal for value in current_line_result.output.values()):
                bulk_logger.info(
                    f"Stop chat since current turn align with stop signal. "
                    f"line number: {line_index}, turn:{turn}. role:{chat_role.role}, name: {chat_role._name}"
                )
                break

        bulk_logger.info(
            f"Finish schedule runs for run id: {run_id}, "
            f"line number: {line_index}, add conversation history to output"
        )
        outputs.update({CONVERSATION_HISTORY_OUTPUT_KEY: conversation_history})

        return LineResult(
            output=outputs,
            aggregation_inputs=aggregation_inputs,
            node_run_infos=current_line_result.node_run_infos,
            run_info=current_line_result.run_info,
        )

    def _process_flow_outputs(
        self,
        index: int,
        chat_role: ChatRole,
        current_line_result: LineResult,
        conversation_history: List[Mapping[str, Any]],
        outputs: dict,
        aggregation_inputs: dict,
    ):

        if CHAT_ROLE_KEY in current_line_result.output:
            message = f"chat role output use reserved key {CHAT_ROLE_KEY}"
            bulk_logger.error(message)
            raise UsingReservedRoleKey(message=message)

        current_turn = {CHAT_ROLE_KEY: chat_role.role}
        current_turn.update(current_line_result.output)
        conversation_history.append(current_turn)

        outputs.update({index: current_turn})
        aggregation_inputs.update({index: current_line_result.aggregation_inputs})

    def _process_batch_inputs(self, inputs: Dict[str, Any]):
        batch_inputs: List = []
        for chat_role in self._chat_group_roles:
            conversation_history_mapping = [
                (key, value)
                for key, value in chat_role._inputs_mapping.items()
                if value == CONVERSATION_HISTORY_EXPRESSION
            ]
            if len(conversation_history_mapping) == 0:
                bulk_logger.error(
                    f"Cannot find conversation expression mapping for "
                    f"chat role: {chat_role.role}. name: {chat_role._name}"
                )
                message = (
                    f"Cannot find conversation expression mapping for "
                    f"chat role: {chat_role.role}. name: {chat_role._name} "
                    f"Please mapping {CONVERSATION_HISTORY_EXPRESSION} for a flow input."
                )
                raise MissingConversationHistoryExpression(message=message)

            if len(conversation_history_mapping) > 1:
                bulk_logger.error(f"Multiple inputs mapping of {CONVERSATION_HISTORY_EXPRESSION}")
                message = (
                    f"chat role: {chat_role.role}. name: {chat_role._name} "
                    f"only accepts 1 inputs mapping for {CONVERSATION_HISTORY_EXPRESSION}"
                )
                raise MultipleConversationHistoryInputsMapping(message=message)

            cleaned_inputs_mapping = {
                key: value
                for key, value in chat_role._inputs_mapping.items()
                if value != CONVERSATION_HISTORY_EXPRESSION
            }

            batch_input_processor = BatchInputsProcessor(
                chat_role._working_dir, chat_role._flow_definition.inputs, self._max_lines_count
            )
            batch_input = batch_input_processor._process_batch_inputs_line(inputs, cleaned_inputs_mapping)
            bulk_logger.info(f"Init conversation history for role: {chat_role.role}")
            batch_input[CONVERSATION_HISTORY_OUTPUT_KEY] = []
            resolved_batch_input = apply_default_value_for_input(chat_role._flow_definition.inputs, batch_input)

            batch_inputs.append(resolved_batch_input)

        return batch_inputs

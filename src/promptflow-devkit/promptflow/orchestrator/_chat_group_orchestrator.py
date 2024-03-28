from typing import Optional, List, Mapping, Dict, Any
from promptflow.contracts.flow import Flow
from promptflow.contracts.chat_group import ChatGroupRole
from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._utils.yaml_utils import load_yaml
from promptflow.batch._base_executor_proxy import AbstractExecutorProxy
from promptflow.executor._result import LineResult
from promptflow.storage import AbstractRunStorage
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
from promptflow._utils.execution_utils import apply_default_value_for_input
from promptflow._proxy._proxy_factory import ProxyFactory


class ChatGroupOrchestrator:
    def __init__(
        self,
        chat_group_roles: List[ChatGroupRole],
        max_turn: Optional[int] = None,
        storage: Optional[AbstractRunStorage] = None,
        max_lines_count: Optional[int] = None,
        **kwargs
    ):
        self._storage = storage
        self._max_turn = max_turn
        self._chat_group_roles = chat_group_roles
        self._max_lines_count = max_lines_count

        self._executor_proxies: List[AbstractExecutorProxy] = self._create_executor_proxy(**kwargs)

    @classmethod
    def create(
        cls,
        chat_group_roles: List[ChatGroupRole],
        max_turn: Optional[int] = None,
        storage: Optional[AbstractRunStorage] = None,
        max_lines_count: Optional[int] = None,
    ) -> "ChatGroupOrchestrator":

        for chat_role in chat_group_roles:
            chat_role.working_dir = Flow._resolve_working_dir(chat_role.flow_file, chat_role.working_dir)
            chat_role.flow = Flow.from_yaml(chat_role.flow_file, working_dir=chat_role.working_dir)

        return ChatGroupOrchestrator(chat_group_roles, max_turn, storage, max_lines_count)

    def _create_executor_proxy(self, **kwargs) -> List[AbstractExecutorProxy]:
        executor_proxy_list = []
        executor_proxy_factory = ProxyFactory()
        for chat_role in self._chat_group_roles:
            executor_proxy = executor_proxy_factory.create_executor_proxy(
                flow_file=chat_role.flow_file,
                working_dir=chat_role.working_dir,
                connections=chat_role.connections,
                storage=self._storage,
                language=self._check_language_from_yaml(chat_role),
                **kwargs
            )
            executor_proxy_list.append(executor_proxy)
        return executor_proxy_list

    async def destroy(self):
        for executor_proxy in self._executor_proxies:
            await executor_proxy.destroy()

    async def _schedule_runs(
            self,
            line_index: int,
            inputs: Mapping[str, Any] = None,
            run_id: str = None,
            ) -> LineResult:

        """schedule runs for a line, submit roleA and format its output as roleB's input.
        Then submit roleB until the max_turn.
        """

        outputs: dict = {}
        aggregation_inputs: dict = {}
        current_line_result: LineResult = None

        total_roles = len(self._chat_group_roles)
        conversation_history: List[Mapping[str, Any]] = []
        batch_inputs = self._process_batch_inputs(inputs)
        for turn in range(self._max_turn):
            role_index = turn % total_roles
            executor_proxy = self._executor_proxies[role_index]
            chat_role = self._chat_group_roles[role_index]
            chat_role_input = batch_inputs[role_index]
            chat_role_input["conversation_history"] = conversation_history
            current_line_result = await executor_proxy.exec_line_async(chat_role_input, line_index, run_id)
            self._process_flow_outputs(
                turn,
                chat_role,
                current_line_result,
                conversation_history,
                outputs,
                aggregation_inputs)
            if any(value == chat_role.stop_signal for value in current_line_result.output.values()):
                break

        return LineResult(
            output=outputs,
            aggregation_inputs=aggregation_inputs,
            node_run_infos=current_line_result.node_run_infos,
            run_info=current_line_result.run_info
        )

    def _check_language_from_yaml(self, flow: ChatGroupRole):
        flow_file = flow.working_dir / flow.flow_file if flow.working_dir else flow.flow_file
        if flow_file.suffix.lower() == ".dll":
            return FlowLanguage.CSharp
        with open(flow_file, "r", encoding="utf-8") as fin:
            flow_dag = load_yaml(fin)
        language = flow_dag.get(LANGUAGE_KEY, FlowLanguage.Python)
        return language

    def _process_flow_outputs(
            self,
            index: int,
            chat_role: ChatGroupRole,
            current_line_result: LineResult,
            conversation_history: List[Mapping[str, Any]],
            outputs: dict,
            aggregation_inputs: dict):

        current_turn = {"role": chat_role.role}
        current_turn.update(current_line_result.output)
        conversation_history.append(current_turn)

        outputs.update({index: current_turn})
        aggregation_inputs.update({index: current_line_result.aggregation_inputs})

    def _process_batch_inputs(self, inputs: Dict[str, Any]):
        batch_inputs: List = []
        for chat_role in self._chat_group_roles:
            batch_input_processor = BatchInputsProcessor(
                chat_role.working_dir,
                chat_role.flow.inputs,
                self._max_lines_count)
            batch_input = batch_input_processor._process_batch_inputs_line(inputs, chat_role.inputs_mapping)
            resolved_batch_input = apply_default_value_for_input(chat_role.flow.inputs, batch_input)
            batch_inputs.append(resolved_batch_input)

        return batch_inputs

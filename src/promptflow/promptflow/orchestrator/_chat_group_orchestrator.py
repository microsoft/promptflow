from typing import Optional, List, Mapping, Any
from promptflow.contracts.flow import ChatGroupRole
from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._utils.yaml_utils import load_yaml
from promptflow.batch._base_executor_proxy import AbstractExecutorProxy
from promptflow._proxy._base_proxy_factory import BaseProxyFactory
from promptflow.batch._single_line_python_executor_proxy import SingleLinePythonExecutorProxy
from promptflow.executor._result import LineResult
from promptflow.storage import AbstractRunStorage

class ChatGroupOrchestrator:
    def __init__(
        self,
        chat_group_roles: List[ChatGroupRole],
        max_turn: Optional[int] = None,
        storage: Optional[AbstractRunStorage] = None,
        **kwargs
    ):
        self._storage = storage
        self._max_turn = max_turn
        self._chat_group_roles = chat_group_roles

        self._executor_proxies: List[AbstractExecutorProxy] = self._create_executor_proxy(**kwargs)

    @classmethod
    def create(
        cls,
        chat_group_roles: List[ChatGroupRole],
        max_turn: Optional[int] = None,
        storage: Optional[AbstractRunStorage] = None,
    ) -> "ChatGroupOrchestrator":

        return ChatGroupOrchestrator(chat_group_roles, max_turn, storage)

    def _create_executor_proxy(self, **kwargs) -> List[AbstractExecutorProxy]:
        executor_proxy_list = []
        executor_proxy_factory = BaseProxyFactory()
        executor_proxy_factory.register_executor("python", SingleLinePythonExecutorProxy)
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
    
    async def _schedule_runs(
            self,
            line_index: int,
            inputs: Mapping[str, Any] = None,
            run_id: str = None,
            chat_roles_inputs: List[List[Mapping[str, Any]]] = None,
            ) -> LineResult:

        """schedule runs for a line, submit roleA and format its output as roleB's input.
        Then submit roleB until the max_turn.
        """
        line_result: LineResult = None
        total_roles = len(self._chat_group_roles)
        conversation_history: List[Mapping[str, Any]] = []
        for turn in range(self._max_turn):
            role_index = turn % total_roles
            executor_proxy = self._executor_proxies[role_index]
            chat_role = self._chat_group_roles[role_index]
            chat_role_input = chat_roles_inputs[role_index]
            chat_role_input[line_index]["conversation_history"] = conversation_history
            line_result = await executor_proxy.exec_line_async(chat_role_input[line_index], line_index, run_id)
            self._process_flow_outputs(chat_role, line_result, conversation_history)
            if any(value == chat_role.stop_signal for value in line_result.output.values()):
                break
            
        return line_result # or latest conversation_history?
        
    def _check_language_from_yaml(self, flow: ChatGroupRole):
        flow_file = flow.working_dir / flow.flow_file if flow.working_dir else flow.flow_file
        if flow_file.suffix.lower() == ".dll":
            return FlowLanguage.CSharp
        with open(flow_file, "r", encoding="utf-8") as fin:
            flow_dag = load_yaml(fin)
        language = flow_dag.get(LANGUAGE_KEY, FlowLanguage.Python)
        return language

    def _process_flow_outputs(self, chat_role: ChatGroupRole, line_result: LineResult, conversation_history: List[Mapping[str, Any]]):
        current_turn = {"role": chat_role.role}
        current_turn.update(line_result.output)
        conversation_history.append(current_turn)
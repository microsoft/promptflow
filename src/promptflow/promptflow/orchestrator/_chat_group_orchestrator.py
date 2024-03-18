from typing import Optional, List, Dict, Mapping, Any
from pathlib import Path
from promptflow.contracts.flow import ChatGroupRole
from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._utils.yaml_utils import load_yaml
from promptflow.batch._base_executor_proxy import APIBasedExecutorProxy
from promptflow.executor._result import LineResult

class ChatGroupOrchestrator:
    def __init__(
        self,
        chat_group_roles: List[ChatGroupRole],
        max_turn: Optional[int] = None,
        **kwargs
    ):
        self._max_turn = max_turn
        self._chat_group_roles = chat_group_roles

        self._kwargs = kwargs
        self._executor_proxies = self._create_executor_proxy()


    def _create_executor_proxy() -> List[APIBasedExecutorProxy]:
        pass
    
    def _schedule_runs(
            self,
            line_index: int = None,
            inputs: Mapping[str, Any] = None,
            run_id: Optional[str] = None,
            **kwargs
            ) -> LineResult:

        """schedule runs for a line, submit roleA and format its output as roleB's input.
        Then submit roleB until the max_turn.
        """
        total_roles = len(self._chat_group_roles)
        conversation_history = []
        for turn in range(self._max_turn):
            role_index = turn % total_roles
            executor_proxy = self._executor_proxies[role_index]
            # resolve current input
            line_result = executor_proxy.exec_line_async(inputs, line_index, run_id)
            conversation_history = self._process_flow_outputs(line_result, conversation_history)
            
        return line_result # or latest conversation_history?
        
    def _check_language_from_yaml(flow: ChatGroupRole):
        pass

    def _process_flow_outputs(self, line_results: LineResult, conversation_history):
        pass
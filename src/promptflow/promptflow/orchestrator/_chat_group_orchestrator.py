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
        input_dirs: Dict[str, str],
        output_dir: Path,
        chat_group_roles: List[ChatGroupRole],
        run_id: Optional[str] = None,
        **kwargs
    ):
        self._input_dirs = input_dirs
        self._output_dir = output_dir
        self._chat_groups = run_id
        self._chat_group_roles = chat_group_roles
        self._kwargs = kwargs
        self._executor_proxies = self._create_executor_proxy()


    def _create_executor_proxy() -> List[APIBasedExecutorProxy]:
        pass
    
    def _schedule_runs(
            self,
            semaphore,
            line_results: List[LineResult],
            line_index: int = None,
            inputs: Mapping[str, Any] = None,
            run_id: Optional[str] = None,
            max_turn: Optional[int] = None,
            **kwargs
            ) -> LineResult:

        """schedule runs for a line, submit roleA and format its output as roleB's input.
        Then submit roleB until the max_turn.
        """
        pass

    async def _exec_line_under_semaphore(
        self,
        semaphore,
        inputs: Mapping[str, Any],
        flow_index: int,
        line_index: Optional[int] = None,
        run_id: Optional[str] = None,
        **kwargs
    ) -> LineResult:
        pass
        
    def _check_language_from_yaml(flow: ChatGroupRole):
        pass
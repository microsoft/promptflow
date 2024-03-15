import asyncio
from typing import Optional, List, Dict, Mapping, Any
from pathlib import Path
from promptflow.contracts.flow import ChatGroupRole
from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._utils.yaml_utils import load_yaml
from promptflow.batch._base_executor_proxy import APIBasedExecutorProxy
from promptflow.batch._base_orchestrator_proxy import BaseOrchestratorProxy
from promptflow.executor._result import LineResult
from promptflow.orchestrator._chat_group_orchestrator import ChatGroupOrchestrator


class ChatGroupOrchestratorProxy(BaseOrchestratorProxy):
    def __init__(
        self,
        **kwargs
    ):
        super().__init__(**kwargs)

    def _create_orchestrator(
        input_dirs: Dict[str, str],
        output_dir: Path,
        chat_group_roles: List[ChatGroupRole],
        run_id: Optional[str] = None,
    ) -> ChatGroupOrchestrator:
        pass
    
    def _orchestrate(
            self,
            semaphore,
            input_dirs: Dict[str, str],
            output_dir: Path,
            chat_group_roles: List[ChatGroupRole],
            batch_inputs: List[Mapping[str, Any]],
            line_results: List[LineResult],
            max_turn: int,
            run_id: Optional[str] = None,
            **kwargs
            ) -> LineResult:

        """schedule runs for a line, submit roleA and format its output as roleB's input.
        Then submit roleB until the max_turn.
        """
        chat_group_orchestrator = self._create_orchestrator(input_dirs, output_dir, chat_group_roles, run_id)

        """
        pending = [
            asyncio.create_task(chat_group_orchestrator._schedule_runs(semaphore, line_results, i, line_inputs, run_id, max_turn))
            for i, line_inputs in enumerate(batch_inputs)
        ]

        """

        pass


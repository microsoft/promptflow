import asyncio
from typing import Optional, List, Dict, Mapping, Any
from pathlib import Path
from promptflow.contracts.flow import ChatGroupRole
from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._utils.yaml_utils import load_yaml
from promptflow.batch._base_executor_proxy import AbstractExecutorProxy
from promptflow.executor._result import LineResult
from promptflow.orchestrator._chat_group_orchestrator import ChatGroupOrchestrator
from promptflow.storage._run_storage import AbstractRunStorage

class ChatGroupOrchestratorProxy(AbstractExecutorProxy):
    def __init__(
        self,
        **kwargs
    ):
        self._orchestrator = None
        super().__init__(**kwargs)

    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        **kwargs,
    ) -> "AbstractExecutorProxy":
        """Create a new executor"""

        chat_group_roles = kwargs.get("chat_group_roles", None)
        max_turn = kwargs.get("max_turn", None)
        run_id = kwargs.get("run_id", None)
        cls._orchestrator = ChatGroupOrchestrator(chat_group_roles, run_id, max_turn)

        pass
    
    async def destroy(self):
        """Destroy the executor"""
        pass

    async def exec_line_async(
        cls,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        """schedule runs for a line, submit roleA and format its output as roleB's input.
        Then submit roleB until the max_turn.
        """
        return cls._orchestrator._schedule_runs(index, inputs, run_id)

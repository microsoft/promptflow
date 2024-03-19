import asyncio
from typing import Optional, List, Dict, Mapping, Any
from pathlib import Path
from promptflow.contracts.flow import ChatGroupRole, Flow
from promptflow._constants import LANGUAGE_KEY, FlowLanguage
from promptflow._utils.yaml_utils import load_yaml
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
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
        self._batch_inputs = None
        super().__init__(**kwargs)

    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        chat_group_roles: Optional[List[ChatGroupRole]] = None,
        max_turn: Optional[int] = None,
        input_dirs: Optional[Dict[str, str]] = None,
        max_lines_count: Optional[int] = None,
    ) -> "AbstractExecutorProxy":
        """Create a new executor"""

        cls._orchestrator = ChatGroupOrchestrator(chat_group_roles, max_turn)
        cls._batch_inputs = cls._process_batch_inputs(chat_group_roles, input_dirs, max_lines_count)
        
        return cls(ChatGroupOrchestratorProxy)
    
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
        return cls._orchestrator._schedule_runs(index, inputs, run_id, cls._batch_inputs[index])
    
    def _process_batch_inputs(
            chat_group_roles: List[ChatGroupRole],
            input_dirs: Dict[str, str],
            max_lines_count: Optional[int] = None) -> List[List[Dict]]:
        
        chat_group_batch_inputs: List[List[Dict]] = []
        
        for chat_role in chat_group_roles:
            chat_role.flow = Flow.from_yaml(chat_role.flow_file, working_dir=chat_role.working_dir)
            flow_inputs = chat_role.flow.inputs
            batch_input_processor = BatchInputsProcessor(chat_role.working_dir, flow_inputs, max_lines_count)
            batch_inputs = batch_input_processor.process_batch_inputs(input_dirs, chat_role.inputs_mapping)
            chat_group_batch_inputs.append(batch_inputs)

        return chat_group_batch_inputs




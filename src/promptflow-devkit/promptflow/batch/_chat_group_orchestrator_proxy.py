from typing import Optional, List, Dict, Mapping, Any
from pathlib import Path
from promptflow.contracts.flow import Flow
from promptflow.contracts.chat_group import ChatGroupRole
from promptflow.batch._batch_inputs_processor import BatchInputsProcessor
from promptflow.batch._base_executor_proxy import AbstractExecutorProxy
from promptflow.executor._result import LineResult
from promptflow.orchestrator._chat_group_orchestrator import ChatGroupOrchestrator
from promptflow.storage._run_storage import AbstractRunStorage


class ChatGroupOrchestratorProxy(AbstractExecutorProxy):
    def __init__(
        self,
        orchestrator: ChatGroupOrchestrator,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._orchestrator = orchestrator
        self._allow_aggregation = False
        self._should_apply_inputs_mapping = False

    @classmethod
    async def create(
        cls,
        flow_file: Path,
        working_dir: Optional[Path] = None,
        *,
        connections: Optional[dict] = None,
        storage: Optional[AbstractRunStorage] = None,
        **kwargs

    ) -> "ChatGroupOrchestratorProxy":
        """Create a new executor"""
        chat_group_roles: List[ChatGroupRole] = kwargs.get("chat_group_roles")
        max_turn = kwargs.get("max_turn")
        max_lines_count = kwargs.get("max_lines_count")

        orchestrator = ChatGroupOrchestrator.create(chat_group_roles, max_turn, storage, max_lines_count)
        return cls(orchestrator)

    async def destroy(self):
        """Destroy the executor"""
        await self._orchestrator.destroy()

    async def exec_line_async(
        self,
        inputs: Mapping[str, Any],
        index: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> LineResult:
        """schedule runs for a line, submit roleA and format its output as roleB's input.
        Then submit roleB until the max_turn.
        """
        return await self._orchestrator._schedule_runs(index, inputs, run_id)

    @classmethod
    def process_batch_inputs(
            cls,
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

        if not chat_group_batch_inputs or not chat_group_batch_inputs[0]:
            return chat_group_batch_inputs

        rows, cols = len(chat_group_batch_inputs), len(chat_group_batch_inputs[0])
        transposed = [[chat_group_batch_inputs[row][col] for row in range(rows)] for col in range(cols)]

        return transposed

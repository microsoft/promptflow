# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from typing import Optional, List, Mapping, Any
from pathlib import Path
from promptflow._proxy._base_executor_proxy import AbstractExecutorProxy
from promptflow.executor._result import LineResult
from promptflow._sdk.entities._chat_group._chat_role import ChatRole
from promptflow._orchestrator._chat_group_orchestrator import ChatGroupOrchestrator
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
        """create chat group orchestrator proxy and required executory proxy for each flow
        :param flow_file: flow file
        :type flow_file: Path
        :param working_dir: flow working directory, defaults to None
        :type working_dir: Optional[Path], optional
        :param connections: connections, defaults to None
        :type connections: Optional[dict], optional
        :param storage: storage, defaults to None
        :type storage: Optional[AbstractRunStorage], optional
        :return: ChatGroupOrchestratorProxy
        :rtype: ChatGroupOrchestratorProxy
        """
        chat_group_roles: List[ChatRole] = kwargs.get("chat_group_roles")
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
        """execute each batch input line
        :param inputs: input line
        :type inputs: Mapping[str, Any]
        :param index: line number, defaults to None
        :type index: Optional[int], optional
        :param run_id: run id, defaults to None
        :type run_id: Optional[str], optional
        :return: line result
        :rtype: LineResult
        """
        return await self._orchestrator._schedule_line_runs(index, inputs, run_id)

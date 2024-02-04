# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
from pathlib import Path
from typing import Any, List, Mapping, Optional

from promptflow._core._errors import MetaFileNotFound, MetaFileReadError
from promptflow._sdk._constants import DEFAULT_ENCODING, FLOW_TOOLS_JSON, PROMPT_FLOW_DIR_NAME
from promptflow.batch._base_executor_proxy import APIBasedExecutorProxy
from promptflow.executor._result import AggregationResult

EXECUTOR_SERVICE_DLL = "Promptflow.dll"


class CSharpBaseExecutorProxy(APIBasedExecutorProxy):
    """Base class for csharp executor proxy for local and runtime."""

    def __init__(
        self,
        *,
        working_dir: Path,
    ):
        self._working_dir = working_dir

    @property
    def working_dir(self) -> Path:
        return self._working_dir

    def _get_flow_meta(self) -> dict:
        # TODO: this should be got from flow.json for all languages by default? If so, we need to promote working_dir
        #  to be a required parameter in the super constructor.
        flow_meta_json_path = self.working_dir / ".promptflow" / "flow.json"
        if not flow_meta_json_path.is_file():
            raise MetaFileNotFound(
                message_format=(
                    # TODO: pf flow validate should be able to generate flow.json
                    "Failed to fetch meta of inputs: cannot find {file_path}, please retry."
                ),
                file_path=flow_meta_json_path.absolute().as_posix(),
            )

        with open(flow_meta_json_path, mode="r", encoding=DEFAULT_ENCODING) as flow_meta_json_path:
            return json.load(flow_meta_json_path)

    async def exec_aggregation_async(
        self,
        batch_inputs: Mapping[str, Any],
        aggregation_inputs: Mapping[str, Any],
        run_id: Optional[str] = None,
    ) -> AggregationResult:
        # TODO: aggregation is not supported for now?
        return AggregationResult({}, {}, {})

    @classmethod
    def _construct_service_startup_command(
        cls,
        port,
        log_path,
        error_file_path,
        yaml_path: str = "flow.dag.yaml",
        log_level: str = "Warning",
        assembly_folder: str = ".",
    ) -> List[str]:
        return [
            "dotnet",
            EXECUTOR_SERVICE_DLL,
            "--execution_service",
            "--port",
            port,
            "--yaml_path",
            yaml_path,
            "--assembly_folder",
            assembly_folder,
            "--log_path",
            log_path,
            "--log_level",
            log_level,
            "--error_file_path",
            error_file_path,
        ]

    @classmethod
    def _get_tool_metadata(cls, flow_file: Path, working_dir: Path) -> dict:
        # TODO: this should be got from flow.tools.json for all languages by default? If so,
        #  we need to promote working_dir to be a required parameter in the super constructor.
        flow_tools_json_path = working_dir / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON
        if flow_tools_json_path.is_file():
            with open(flow_tools_json_path, mode="r", encoding=DEFAULT_ENCODING) as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    raise MetaFileReadError(
                        message_format="Failed to fetch meta of tools: {file_path} is not a valid json file.",
                        file_path=flow_tools_json_path.absolute().as_posix(),
                    )
        raise MetaFileNotFound(
            message_format=(
                "Failed to fetch meta of tools: cannot find {file_path}, please build the flow project first."
            ),
            file_path=flow_tools_json_path.absolute().as_posix(),
        )

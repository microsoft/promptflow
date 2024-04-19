# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from typing import Any, List, Mapping, Optional

from promptflow._proxy._base_executor_proxy import APIBasedExecutorProxy
from promptflow.executor._result import AggregationResult

EXECUTOR_SERVICE_DLL = "Promptflow.dll"


class CSharpBaseExecutorProxy(APIBasedExecutorProxy):
    """Base class for csharp executor proxy for local and runtime."""

    def __init__(
        self,
        *,
        working_dir: Path = None,
        enable_stream_output: bool = False,
    ):
        super().__init__(working_dir=working_dir, enable_stream_output=enable_stream_output)

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
        init_kwargs_path: str = None,
        **kwargs,
    ) -> List[str]:
        cmd = [
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
        if init_kwargs_path:
            cmd.extend(["--init", init_kwargs_path])
        return cmd

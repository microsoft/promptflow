# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import base64
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping

from promptflow._utils.multimedia_utils import persist_multimedia_data
from promptflow.executor import FlowExecutor, FlowValidator
from promptflow.executor._result import AggregationResult
from promptflow.parallel._config.model import ParallelRunConfig
from promptflow.parallel._executor.input_mapping import InputMapping
from promptflow.parallel._model import Result, Row
from promptflow.tracing._operation_context import OperationContext


class ParallelRunExecutor(ABC):
    @abstractmethod
    def init(self):
        raise NotImplementedError

    @abstractmethod
    def execute(self, row: Row) -> Result:
        raise NotImplementedError

    @abstractmethod
    def execute_aggregation(
        self, inputs: Mapping[str, Any], aggregation_inputs: Mapping[str, Any]
    ) -> AggregationResult:
        raise NotImplementedError

    @property
    @abstractmethod
    def has_aggregation_node(self):
        raise NotImplementedError


class AbstractExecutor(ParallelRunExecutor, ABC):
    def __init__(self, working_dir: Path, config: ParallelRunConfig):
        self._validate_config(config)
        self._working_dir = working_dir
        self._config = config
        self._input_mapping = InputMapping(config.input_dir, config.side_input_dir, config.input_mapping)
        self._flow_executor = self._create_flow_executor(self._resolve_connections_from_env(), config)

    def _validate_config(self, config: ParallelRunConfig):
        assert config.input_dir is not None, "No input asset found."

    @abstractmethod
    def _create_flow_executor(self, connections: dict, config: ParallelRunConfig) -> FlowExecutor:
        raise NotImplementedError

    @staticmethod
    def _resolve_connections_from_env() -> dict:
        conn_json_b64 = os.getenv("AML_PROMPT_FLOW_CONNECTIONS")
        connections = (
            json.loads(base64.b64decode(conn_json_b64.encode("utf-8")).decode("utf-8")) if conn_json_b64 else {}
        )
        FlowExecutor.update_environment_variables_with_connections(connections)
        return connections

    def init(self):
        self._setup_context(OperationContext.get_instance())
        os.chdir(self._resolve_working_dir())

    def _setup_context(self, context: OperationContext):
        from promptflow._utils.execution_utils import set_batch_input_source_from_inputs_mapping

        context.append_user_agent("ParallelComputing")
        set_batch_input_source_from_inputs_mapping(self._config.input_mapping)

    def _resolve_working_dir(self) -> Path:
        return self._working_dir

    def execute(self, row: Row) -> Result:
        row = self._input_mapping.apply(row)
        inputs = FlowValidator.resolve_flow_inputs_type(self._flow_executor._flow, row)
        executor_result = self._flow_executor.exec_line(inputs, index=row.row_number)
        executor_result.output = persist_multimedia_data(executor_result.output, base_dir=self._config.output_dir)
        return Result(Row.from_dict(inputs, row_number=row.row_number), executor_result)

    def execute_aggregation(
        self, inputs: Mapping[str, Any], aggregation_inputs: Mapping[str, Any]
    ) -> AggregationResult:
        return self._flow_executor.exec_aggregation(inputs, aggregation_inputs)

    @property
    def _flow_dag(self):
        return self._resolve_working_dir() / "flow.dag.yaml"

    @property
    def has_aggregation_node(self):
        return self._flow_executor.has_aggregation_node

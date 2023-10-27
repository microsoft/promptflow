# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
from functools import partial
from pathlib import Path
from typing import Union

from promptflow._sdk._constants import ConnectionType
from promptflow._sdk._errors import ConnectionNotFoundError
from promptflow._sdk.operations._local_storage_operations import NodeRunRecord
from promptflow._sdk.operations._test_submitter import TestSubmitter
from promptflow._utils.tool_utils import get_inputs_for_prompt_template
from promptflow.contracts.flow import Node, ToolSourceType
from promptflow.contracts.run_info import RunInfo as NodeRunInfo
from promptflow.exceptions import ErrorTarget, PromptflowException, UserErrorException
from promptflow.executor._errors import ResolveToolError
from promptflow.executor._tool_resolver import ResolvedTool, ToolType
from promptflow.executor.flow_executor import LineResult

from .tool_record import just_return, record_node_run


def mock_update_run_func(self, run_info):
    run_id = run_info.run_id
    run_info.api_calls = self._collect_traces_from_nodes(run_id)
    child_run_infos = self.collect_child_node_runs(run_id)
    run_info.system_metrics = run_info.system_metrics or {}
    run_info.system_metrics.update(self.collect_metrics(child_run_infos, self.OPENAI_AGGREGATE_METRICS))
    run_info.system_metrics["total_tokens"] = 0


def mock_persist_node_run(recording_folder: Path):
    def _mock_persist_node_run(self, run_info: NodeRunInfo) -> None:
        node_run_record = NodeRunRecord.from_run_info(run_info)
        node_folder = self._prepare_folder(self._node_infos_folder / node_run_record.NodeName)
        # for reduce nodes, the line_number is None, store the info in the 000000000.jsonl
        # align with AzureMLRunStorageV2, which is a storage contract with PFS
        line_number = 0 if node_run_record.line_number is None else node_run_record.line_number
        filename = f"{str(line_number).zfill(self.LINE_NUMBER_WIDTH)}.jsonl"
        node_run_record.dump(node_folder / filename, run_name=self._run.name)
        record_node_run(node_run_record.run_info, recording_folder)

    return _mock_persist_node_run


def mock_flowoperations_test(recording_folder: Path):
    def _mock_flowoperations_test(
        self,
        flow: Union[str, os.PathLike],
        *,
        inputs: dict = None,
        variant: str = None,
        node: str = None,
        environment_variables: dict = None,
        stream_log: bool = True,
        allow_generator_output: bool = True,
        **kwargs,
    ):
        """Test flow or node.

        :param flow: path to flow directory to test
        :param inputs: Input data for the flow test
        :param variant: Node & variant name in format of ${node_name.variant_name}, will use default variant
        if not specified.
        :param node: If specified it will only test this node, else it will test the flow.
        :param environment_variables: Environment variables to set by specifying a property path and value.
        Example: {"key1": "${my_connection.api_key}", "key2"="value2"}
        The value reference to connection keys will be resolved to the actual value,
        and all environment variables specified will be set into os.environ.
        : param allow_generator_output: Whether return streaming output when flow has streaming output.
        :return: Executor result
        """
        from promptflow._sdk._load_functions import load_flow

        inputs = inputs or {}
        flow = load_flow(flow)
        config = kwargs.get("config", None)
        with TestSubmitter(flow=flow, variant=variant, config=config).init() as submitter:
            is_chat_flow, chat_history_input_name, _ = self._is_chat_flow(submitter.dataplane_flow)
            flow_inputs, dependency_nodes_outputs = submitter._resolve_data(
                node_name=node, inputs=inputs, chat_history_name=chat_history_input_name
            )

            if node:
                result: NodeRunInfo = submitter.node_test(
                    node_name=node,
                    flow_inputs=flow_inputs,
                    dependency_nodes_outputs=dependency_nodes_outputs,
                    environment_variables=environment_variables,
                    stream=True,
                )
                record_node_run(result, recording_folder)
                return result
            else:
                result_flow_test: LineResult = submitter.flow_test(
                    inputs=flow_inputs,
                    environment_variables=environment_variables,
                    stream_log=stream_log,
                    allow_generator_output=allow_generator_output and is_chat_flow,
                )
                record_node_run(result_flow_test.run_info, recording_folder)
                return result_flow_test

    return _mock_flowoperations_test


def mock_bulkresult_get_openai_metrics(self):
    # Some tests request the metrics in replay mode.
    total_metrics = {"total_tokens": 0, "duration": 0}
    return total_metrics


def mock_toolresolver_resolve_tool_by_node(recording_folder: Path):
    def _resolve_replay_node(self, node: Node, convert_input_types=False) -> ResolvedTool:
        # in replay mode, replace original tool with just_return tool
        # the tool itself just return saved record from storage_record.json
        # processing no logic.
        if (node.api == "completion" or node.api == "chat") and (
            node.connection == "azure_open_ai_connection" or node.provider == "AzureOpenAI"
        ):
            prompt_tpl = self._load_source_content(node)
            prompt_tpl_inputs = get_inputs_for_prompt_template(prompt_tpl)
            callable = partial(just_return, "AzureOpenAI", prompt_tpl, prompt_tpl_inputs, recording_folder)
            return ResolvedTool(node=node, definition=None, callable=callable, init_args={})
        else:
            return None

    def _mock_toolresolver_resolve_tool_by_node(self, node: Node, convert_input_types=True) -> ResolvedTool:
        try:
            if node.source is None:
                raise UserErrorException(f"Node {node.name} does not have source defined.")

            if node.type is ToolType.PYTHON:
                if node.source.type == ToolSourceType.Package:
                    return self._resolve_package_node(node, convert_input_types=convert_input_types)
                elif node.source.type == ToolSourceType.Code:
                    return self._resolve_script_node(node, convert_input_types=convert_input_types)
                raise NotImplementedError(f"Tool source type {node.source.type} for python tool is not supported yet.")
            elif node.type is ToolType.PROMPT:
                return self._resolve_prompt_node(node)
            elif node.type is ToolType.LLM:
                resolved_tool = _resolve_replay_node(self, node, convert_input_types=convert_input_types)
                if resolved_tool is None:
                    resolved_tool = self._resolve_llm_node(node, convert_input_types=convert_input_types)
                return resolved_tool
            elif node.type is ToolType.CUSTOM_LLM:
                if node.source.type == ToolSourceType.PackageWithPrompt:
                    resolved_tool = self._resolve_package_node(node, convert_input_types=convert_input_types)
                    return self._integrate_prompt_in_package_node(node, resolved_tool)
                raise NotImplementedError(
                    f"Tool source type {node.source.type} for custom_llm tool is not supported yet."
                )
            else:
                raise NotImplementedError(f"Tool type {node.type} is not supported yet.")
        except Exception as e:
            if isinstance(e, PromptflowException) and e.target != ErrorTarget.UNKNOWN:
                raise ResolveToolError(node_name=node.name, target=e.target, module=e.module) from e
            raise ResolveToolError(node_name=node.name) from e

    return _mock_toolresolver_resolve_tool_by_node


def mock_get_local_connections_from_executable(executable, client):
    connection_names = executable.get_connection_names()
    result = {}
    for n in connection_names:
        try:
            conn = client.connections.get(name=n, with_secrets=True)
            if conn is not None and conn.TYPE == ConnectionType.AZURE_OPEN_AI and conn.api_base == "dummy_base":
                return {}
            result[n] = conn._to_execution_connection_dict()
        except ConnectionNotFoundError:
            return {}
    return result

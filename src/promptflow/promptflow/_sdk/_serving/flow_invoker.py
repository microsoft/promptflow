# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Callable, Union

from promptflow import PFClient
from promptflow._constants import LINE_NUMBER_KEY
from promptflow._sdk._load_functions import load_flow
from promptflow._sdk._serving._errors import UnexpectedConnectionProviderReturn, UnsupportedConnectionProvider
from promptflow._sdk._serving.flow_result import FlowResult
from promptflow._sdk._serving.utils import validate_request_data
from promptflow._sdk._utils import (
    dump_flow_result,
    get_local_connections_from_executable,
    override_connection_config_with_environment_variable,
    resolve_connections_environment_variable_reference,
    update_environment_variables_with_connections,
)
from promptflow._sdk.entities._connection import _Connection
from promptflow._sdk.entities._flow import Flow
from promptflow._sdk.operations._flow_operations import FlowOperations
from promptflow._utils.logger_utils import LoggerFactory
from promptflow._utils.multimedia_utils import convert_multimedia_data_to_base64, persist_multimedia_data
from promptflow.contracts.flow import Flow as ExecutableFlow
from promptflow.executor import FlowExecutor
from promptflow.storage._run_storage import DefaultRunStorage


class FlowInvoker:
    """
    The invoker of a flow.

    :param flow: The path of the flow, or the flow loaded by load_flow().
    :type flow: [str, ~promptflow._sdk.entities._flow.Flow]
    :param connection_provider: The connection provider, defaults to None
    :type connection_provider: [str, Callable], optional
    :param streaming: The function or bool to determine enable streaming or not, defaults to lambda: False
    :type streaming: Union[Callable[[], bool], bool], optional
    :param connections: Pre-resolved connections used when executing, defaults to None
    :type connections: dict, optional
    :param connections_name_overrides: The connection name overrides, defaults to None
        Example: ``{"aoai_connection": "azure_open_ai_connection"}``
        The node with reference to connection 'aoai_connection' will be resolved to the actual connection 'azure_open_ai_connection'. # noqa: E501
    :type connections_name_overrides: dict, optional
    :param raise_ex: Whether to raise exception when executing flow, defaults to True
    :type raise_ex: bool, optional
    """

    def __init__(
        self,
        flow: [str, Flow],
        connection_provider: [str, Callable] = None,
        streaming: Union[Callable[[], bool], bool] = False,
        connections: dict = None,
        connections_name_overrides: dict = None,
        raise_ex: bool = True,
        **kwargs,
    ):
        self.logger = kwargs.get("logger", LoggerFactory.get_logger("flowinvoker"))
        self.flow_entity = flow if isinstance(flow, Flow) else load_flow(source=flow)
        self._executable_flow = ExecutableFlow._from_dict(
            flow_dag=self.flow_entity._data, working_dir=self.flow_entity.code
        )
        self.connections = connections or {}
        self.connections_name_overrides = connections_name_overrides or {}
        self.raise_ex = raise_ex
        self.storage = kwargs.get("storage", None)
        self.streaming = streaming if isinstance(streaming, Callable) else lambda: streaming
        # Pass dump_to path to dump flow result for extension.
        self._dump_to = kwargs.get("dump_to", None)
        # The credential is used as an option to override
        # DefaultAzureCredential when using workspace connection provider
        self._credential = kwargs.get("credential", None)

        self._init_connections(connection_provider)
        self._init_executor()
        self.flow = self.executor._flow
        self._dump_file_prefix = "chat" if self._is_chat_flow else "flow"

    def _init_connections(self, connection_provider):
        self._is_chat_flow, _, _ = FlowOperations._is_chat_flow(self._executable_flow)
        connection_provider = "local" if connection_provider is None else connection_provider
        if isinstance(connection_provider, str):
            self.logger.info(f"Getting connections from pf client with provider {connection_provider}...")
            connections_to_ignore = list(self.connections.keys())
            connections_to_ignore.extend(self.connections_name_overrides.keys())
            # Note: The connection here could be local or workspace, depends on the connection.provider in pf.yaml.
            connections = get_local_connections_from_executable(
                executable=self._executable_flow,
                client=PFClient(config={"connection.provider": connection_provider}, credential=self._credential),
                connections_to_ignore=connections_to_ignore,
                # fetch connections with name override
                connections_to_add=list(self.connections_name_overrides.values()),
            )
            # use original name for connection with name override
            override_name_to_original_name_mapping = {v: k for k, v in self.connections_name_overrides.items()}
            for name, conn in connections.items():
                if name in override_name_to_original_name_mapping:
                    self.connections[override_name_to_original_name_mapping[name]] = conn
                else:
                    self.connections[name] = conn
        elif isinstance(connection_provider, Callable):
            self.logger.info("Getting connections from custom connection provider...")
            connection_list = connection_provider()
            if not isinstance(connection_list, list):
                raise UnexpectedConnectionProviderReturn(
                    f"Connection provider {connection_provider} should return a list of connections."
                )
            if any(not isinstance(item, _Connection) for item in connection_list):
                raise UnexpectedConnectionProviderReturn(
                    f"All items returned by {connection_provider} should be connection type, got {connection_list}."
                )
            # TODO(2824058): support connection provider when executing function
            connections = {item.name: item.to_execution_connection_dict() for item in connection_list}
            self.connections.update(connections)
        else:
            raise UnsupportedConnectionProvider(connection_provider)

        override_connection_config_with_environment_variable(self.connections)
        resolve_connections_environment_variable_reference(self.connections)
        update_environment_variables_with_connections(self.connections)
        self.logger.info(f"Promptflow get connections successfully. keys: {self.connections.keys()}")

    def _init_executor(self):
        self.logger.info("Promptflow executor starts initializing...")
        storage = None
        if self._dump_to:
            storage = DefaultRunStorage(base_dir=self._dump_to, sub_dir=Path(".promptflow/intermediate"))
        else:
            storage = self.storage
        self.executor = FlowExecutor._create_from_flow(
            flow=self._executable_flow,
            working_dir=self.flow_entity.code,
            connections=self.connections,
            raise_ex=self.raise_ex,
            storage=storage,
        )
        self.executor.enable_streaming_for_llm_flow(self.streaming)
        self.logger.info("Promptflow executor initiated successfully.")

    def _invoke(self, data: dict, run_id=None, disable_input_output_logging=False):
        """
        Process a flow request in the runtime.

        :param data: The request data dict with flow input as keys, for example: {"question": "What is ChatGPT?"}.
        :type data: dict
        :param run_id: The run id of the flow request, defaults to None
        :type run_id: str, optional
        :return: The result of executor.
        :rtype: ~promptflow.executor._result.LineResult
        """
        log_data = "<REDACTED>" if disable_input_output_logging else data
        self.logger.info(f"Validating flow input with data {log_data!r}")
        validate_request_data(self.flow, data)
        self.logger.info(f"Execute flow with data {log_data!r}")
        # Pass index 0 as extension require for dumped result.
        # TODO: Remove this index after extension remove this requirement.
        result = self.executor.exec_line(data, index=0, run_id=run_id, allow_generator_output=self.streaming())
        if LINE_NUMBER_KEY in result.output:
            # Remove line number from output
            del result.output[LINE_NUMBER_KEY]
        return result

    def invoke(self, data: dict, run_id=None, disable_input_output_logging=False):
        """
        Process a flow request in the runtime and return the output of the executor.

        :param data: The request data dict with flow input as keys, for example: {"question": "What is ChatGPT?"}.
        :type data: dict
        :return: The flow output dict, for example: {"answer": "ChatGPT is a chatbot."}.
        :rtype: dict
        """
        result = self._invoke(data, run_id=run_id, disable_input_output_logging=disable_input_output_logging)
        # Get base64 for multi modal object
        resolved_outputs = self._convert_multimedia_data_to_base64(result)
        self._dump_invoke_result(result)
        log_outputs = "<REDACTED>" if disable_input_output_logging else result.output
        self.logger.info(f"Flow run result: {log_outputs}")
        if not self.raise_ex:
            # If raise_ex is False, we will return the trace flow & node run info.
            return FlowResult(
                output=resolved_outputs or {},
                run_info=result.run_info,
                node_run_infos=result.node_run_infos,
            )
        return resolved_outputs

    def _convert_multimedia_data_to_base64(self, invoke_result):
        resolved_outputs = {
            k: convert_multimedia_data_to_base64(v, with_type=True, dict_type=True)
            for k, v in invoke_result.output.items()
        }
        return resolved_outputs

    def _dump_invoke_result(self, invoke_result):
        if self._dump_to:
            invoke_result.output = persist_multimedia_data(
                invoke_result.output, base_dir=self._dump_to, sub_dir=Path(".promptflow/output")
            )
            dump_flow_result(flow_folder=self._dump_to, flow_result=invoke_result, prefix=self._dump_file_prefix)

# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import dataclasses
import os
from pathlib import Path
from typing import Callable, Union

from promptflow._utils.dataclass_serializer import convert_eager_flow_output_to_dict
from promptflow._utils.flow_utils import dump_flow_result, is_executable_chat_flow
from promptflow._utils.logger_utils import LoggerFactory
from promptflow._utils.multimedia_utils import MultimediaProcessor
from promptflow.contracts.run_info import Status
from promptflow.core._connection import _Connection
from promptflow.core._connection_provider._connection_provider import ConnectionProvider
from promptflow.core._flow import AbstractFlowBase
from promptflow.core._serving._errors import UnexpectedConnectionProviderReturn, UnsupportedConnectionProvider
from promptflow.core._serving.flow_result import FlowResult
from promptflow.core._serving.utils import validate_request_data
from promptflow.core._utils import (
    init_executable,
    override_connection_config_with_environment_variable,
    resolve_connections_environment_variable_reference,
    update_environment_variables_with_connections,
)
from promptflow.executor import FlowExecutor
from promptflow.storage._run_storage import DefaultRunStorage


class FlowInvoker:
    """
    The invoker of a flow.

    :param flow: A loaded Flow object.
    :type flow: Flow
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
    :param init_kwargs: Class init arguments for callable class, only supported for flex flow.
    :type init_kwargs: dict, optional
    """

    def __init__(
        self,
        flow: AbstractFlowBase,
        connection_provider: [str, Callable] = None,
        streaming: Union[Callable[[], bool], bool] = False,
        connections: dict = None,
        connections_name_overrides: dict = None,
        raise_ex: bool = True,
        init_kwargs: dict = None,
        **kwargs,
    ):
        self.logger = kwargs.get("logger", LoggerFactory.get_logger("flowinvoker"))
        self._init_kwargs = init_kwargs or {}
        self.logger.debug(f"Init flow invoker with init kwargs: {self._init_kwargs}")
        # TODO: avoid to use private attribute after we finalize the inheritance
        self.flow = init_executable(working_dir=flow._code, flow_path=flow._path)
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
        # TODO: avoid to use private attribute after we finalize the inheritance
        self._init_executor(flow._path, flow._code)
        self._dump_file_prefix = "chat" if self._is_chat_flow else "flow"
        self._multimedia_processor = MultimediaProcessor.create(self.flow.message_format)
        self._disable_serialization = os.getenv("PF_DISABLE_SERIALIZATION", "False").lower() == "true"

    def resolve_connections(
        self,
        connection_names,
        provider,
        *,
        raise_error=False,
        connections_to_ignore=None,
        connections_to_add=None,
    ):
        """Resolve connections required by flow, get connections from provider."""
        connection_names = set(connection_names)
        if connections_to_add:
            connection_names.update(connections_to_add)
        result = {}
        for name in connection_names:
            if connections_to_ignore and name in connections_to_ignore:
                continue
            try:
                conn = provider.get(name=name)
                result[name] = conn._to_execution_connection_dict()
            except Exception as e:
                if raise_error:
                    raise e
        return result

    def _init_connections(self, connection_provider):
        self._is_chat_flow, _, _ = is_executable_chat_flow(self.flow)

        if connection_provider is None or isinstance(connection_provider, str):
            self.logger.info(f"Getting connections from pf client with provider from args: {connection_provider}...")
            connections_to_ignore = list(self.connections.keys())
            self.logger.debug(f"Flow invoker connections: {self.connections.keys()}")
            connections_to_ignore.extend(self.connections_name_overrides.keys())
            self.logger.debug(f"Flow invoker connections name overrides: {self.connections_name_overrides.keys()}")
            self.logger.debug(f"Ignoring connections: {connections_to_ignore}")
            if not connection_provider:
                # If user not pass in connection provider string, get from environment variable.
                connection_provider = ConnectionProvider.get_instance(credential=self._credential)
            else:
                # Else, init from the string to parse the provider config.
                connection_provider = ConnectionProvider.init_from_provider_config(
                    connection_provider, credential=self._credential
                )
            # Note: The connection here could be local or workspace, depends on the connection.provider in pf.yaml.
            connections = self.resolve_connections(
                # use os.environ to override flow definition's connection since
                # os.environ is resolved to user's setting now
                connection_names=self.flow.get_connection_names(
                    environment_variables_overrides=os.environ,
                ),
                provider=connection_provider,
                connections_to_ignore=connections_to_ignore,
                # fetch connections with name override
                connections_to_add=list(self.connections_name_overrides.values()),
                raise_error=True,
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

    def _init_executor(self, flow_path, working_dir):
        self.logger.info("Promptflow executor starts initializing...")
        storage = None
        if self._dump_to:
            storage = DefaultRunStorage(base_dir=self._dump_to, sub_dir=Path(".promptflow/intermediate"))
        else:
            storage = self.storage
        self.executor = FlowExecutor.create(
            flow_file=flow_path,
            working_dir=working_dir,
            connections=self.connections,
            raise_ex=self.raise_ex,
            storage=storage,
            init_kwargs=self._init_kwargs,
            env_exporter_setup=False,
        )
        self.executor.enable_streaming_for_llm_flow(self.streaming)
        self.logger.info("Promptflow executor initiated successfully.")

    def _invoke_context(self, data: dict, disable_input_output_logging=False):
        log_data = "<REDACTED>" if disable_input_output_logging else data
        self.logger.info(f"Validating flow input with data {log_data!r}")
        validate_request_data(self.flow, data)
        self.logger.info(f"Execute flow with data {log_data!r}")

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
        self._invoke_context(data, disable_input_output_logging)
        return self.executor.exec_line(data, run_id=run_id, allow_generator_output=self.streaming())

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
        output_dict = convert_eager_flow_output_to_dict(result.output)
        if not isinstance(result.output, dict) and not dataclasses.is_dataclass(result.output):
            returned_non_dict_output = True
        else:
            returned_non_dict_output = False
        resolved_outputs = self._convert_multimedia_data_to_base64(output_dict)
        self._dump_invoke_result(result)
        if result.run_info.status != Status.Completed:
            self.logger.error(f"Flow run failed with error: {result.run_info.error}")
        else:
            log_outputs = "<REDACTED>" if disable_input_output_logging else result.output
            self.logger.info(f"Flow run result: {log_outputs}")
        if not self.raise_ex:
            # If raise_ex is False, we will return the trace flow & node run info.
            return FlowResult(
                output=resolved_outputs or {},
                run_info=result.run_info,
                node_run_infos=result.node_run_infos,
                response_original_value=returned_non_dict_output,
            )
        return resolved_outputs

    def _convert_multimedia_data_to_base64(self, output_dict):
        resolved_outputs = {
            k: self._multimedia_processor.convert_multimedia_data_to_base64_dict(v) for k, v in output_dict.items()
        }
        return resolved_outputs

    def _dump_invoke_result(self, invoke_result):
        if self._dump_to:
            invoke_result.output = self._multimedia_processor.persist_multimedia_data(
                invoke_result.output, base_dir=self._dump_to, sub_dir=Path(".promptflow/output")
            )

            dump_flow_result(flow_folder=self._dump_to, flow_result=invoke_result, prefix=self._dump_file_prefix)


class AsyncFlowInvoker(FlowInvoker):
    async def _invoke_async(self, data: dict, run_id=None, disable_input_output_logging=False):
        self._invoke_context(data, disable_input_output_logging)
        return await self.executor.exec_line_async(data, run_id=run_id, allow_generator_output=self.streaming())

    async def invoke_async(self, data: dict, run_id=None, disable_input_output_logging=False):
        result = await self._invoke_async(
            data, run_id=run_id, disable_input_output_logging=disable_input_output_logging
        )
        # Get base64 for multi modal object
        output_dict = convert_eager_flow_output_to_dict(result.output)
        if not isinstance(result.output, dict) and not dataclasses.is_dataclass(result.output):
            returned_non_dict_output = True
        else:
            returned_non_dict_output = False
        resolved_outputs = self._convert_multimedia_data_to_base64(output_dict)
        self._dump_invoke_result(result)
        if result.run_info.status != Status.Completed:
            self.logger.error(f"Flow run failed with error: {result.run_info.error}")
        else:
            log_outputs = "<REDACTED>" if disable_input_output_logging else result.output
            self.logger.info(f"Flow run result: {log_outputs}")
        if not self.raise_ex:
            # If raise_ex is False, we will return the trace flow & node run info.
            return FlowResult(
                output=resolved_outputs or {},
                run_info=result.run_info,
                node_run_infos=result.node_run_infos,
                response_original_value=returned_non_dict_output,
            )
        return resolved_outputs

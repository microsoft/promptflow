# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
from typing import Callable, Union

from promptflow._sdk._constants import LOGGER_NAME
from promptflow._sdk._serving._errors import UnexpectedConnectionProviderReturn, UnsupportedConnectionProvider
from promptflow._sdk._serving.utils import validate_request_data
from promptflow._sdk._utils import update_environment_variables_with_connections
from promptflow._sdk.entities._connection import _Connection
from promptflow._sdk.entities._flow import Flow
from promptflow.executor import FlowExecutor

logger = logging.getLogger(LOGGER_NAME)


class FlowInvoker:
    """
    The invoker of a flow.

    :param flow: The path of the flow.
    :type flow: str
    :param connection_provider: The connection provider, defaults to None
    :type connection_provider: [str, Callable], optional
    :param streaming: The function or bool to determine enable streaming or not, defaults to lambda: False
    :type streaming: Union[Callable[[], bool], bool], optional
    """

    def __init__(
        self, flow: str, connection_provider: [str, Callable] = None, streaming: Union[Callable[[], bool], bool] = False
    ):
        self.flow_dir = flow
        self.flow_entity = Flow.load(self.flow_dir)
        self.streaming = streaming if isinstance(streaming, Callable) else lambda: streaming
        self._init_connections(connection_provider)
        self._init_executor()
        self.flow = self.executor._flow

    def _init_connections(self, connection_provider):
        if connection_provider == "local":
            logger.info("Getting connections from local sqlite...")
            self.connections = Flow._get_local_connections(executable=self.flow_entity._init_executable())
        elif connection_provider == "azure":
            # TODO: support this
            raise NotImplementedError("Azure connection provider is not supported yet.")
        elif isinstance(connection_provider, Callable):
            logger.info("Getting connections from custom connection provider...")
            connection_list = connection_provider()
            if not isinstance(connection_list, list):
                raise UnexpectedConnectionProviderReturn(
                    f"Connection provider {connection_provider} should return a list of connections."
                )
            if any(not isinstance(item, _Connection) for item in connection_list):
                raise UnexpectedConnectionProviderReturn(
                    f"All items returned by {connection_provider} should be connection type, got {connection_list}."
                )
            self.connections = {item.name: item.to_execution_connection_dict() for item in connection_list}
        else:
            raise UnsupportedConnectionProvider(connection_provider)

    def _init_executor(self):
        logger.info("Promptflow executor starts initializing...")
        # try to get the connections
        logger.info("Promptflow start getting connections from local...")

        update_environment_variables_with_connections(self.connections)
        logger.info(f"Promptflow serving app get connections successfully. keys: {self.connections.keys()}")
        self.executor = FlowExecutor.create(
            flow_file=self.flow_entity.path,
            working_dir=self.flow_entity.code,
            connections=self.connections,
            raise_ex=True,
        )
        self.executor.enable_streaming_for_llm_flow(self.streaming)
        logger.info("Promptflow executor initiated successfully.")

    def invoke(self, data):
        """process a flow request in the runtime."""
        logger.info(f"PromptFlow invoker received data: {data}")

        logger.info(f"Validating flow input with data {data!r}")
        validate_request_data(self.flow, data)
        logger.info(f"Execute flow with data {data!r}")
        result = self.executor.exec_line(data, allow_generator_output=self.streaming())
        return result.output

# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import logging
import os
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Union

import pandas as pd

from ._configuration import Configuration
from ._constants import LOGGER_NAME, MAX_SHOW_DETAILS_RESULTS, ConnectionProvider
from ._logger_factory import LoggerFactory
from ._user_agent import USER_AGENT
from ._utils import setup_user_agent_to_operation_context
from .entities import Run
from .operations import RunOperations
from .operations._connection_operations import ConnectionOperations
from .operations._flow_operations import FlowOperations
from .operations._tool_operations import ToolOperations
from .operations._local_azure_connection_operations import LocalAzureConnectionOperations

logger = LoggerFactory.get_logger(name=LOGGER_NAME, verbosity=logging.WARNING)


def _create_run(run: Run, **kwargs):
    client = PFClient()
    return client.runs.create_or_update(run=run, **kwargs)


class PFClient:
    """A client class to interact with prompt flow entities."""

    def __init__(self):
        self._runs = RunOperations()
        self._connection_provider = None
        # Lazy init to avoid azure credential requires too early
        self._connections = None
        self._flows = FlowOperations()
        self._tools = ToolOperations()
        setup_user_agent_to_operation_context(USER_AGENT)

    def run(
        self,
        flow: Union[str, PathLike],
        *,
        data: Union[str, PathLike] = None,
        run: Union[str, Run] = None,
        column_mapping: dict = None,
        variant: str = None,
        connections: dict = None,
        environment_variables: dict = None,
        name: str = None,
        display_name: str = None,
        tags: Dict[str, str] = None,
        **kwargs,
    ) -> Run:
        """Run flow against provided data or run.

        .. note::
            At least one of the ``data`` or ``run`` parameters must be provided.

        .. admonition:: Column_mapping

            Column mapping is a mapping from flow input name to specified values.
            If specified, the flow will be executed with provided value for specified inputs.
            The value can be:

            - from data:
                - ``data.col1``
            - from run:
                - ``run.inputs.col1``: if need reference run's inputs
                - ``run.output.col1``: if need reference run's outputs
            - Example:
                - ``{"ground_truth": "${data.answer}", "prediction": "${run.outputs.answer}"}``

        :param flow: Path to the flow directory to run evaluation.
        :type flow: Union[str, PathLike]
        :param data: Pointer to the test data (of variant bulk runs) for eval runs.
        :type data: Union[str, PathLike]
        :param run: Flow run ID or flow run. This parameter helps keep lineage between
            the current run and variant runs. Batch outputs can be
            referenced as ``${run.outputs.col_name}`` in inputs_mapping.
        :type run: Union[str, ~promptflow.entities.Run]
        :param column_mapping: Define a data flow logic to map input data.
        :type column_mapping: Dict[str, str]
        :param variant: Node & variant name in the format of ``${node_name.variant_name}``.
            The default variant will be used if not specified.
        :type variant: str
        :param connections: Overwrite node level connections with provided values.
            Example: ``{"node1": {"connection": "new_connection", "deployment_name": "gpt-35-turbo"}}``
        :type connections: Dict[str, Dict[str, str]]
        :param environment_variables: Environment variables to set by specifying a property path and value.
            Example: ``{"key1": "${my_connection.api_key}", "key2"="value2"}``
            The value reference to connection keys will be resolved to the actual value,
            and all environment variables specified will be set into os.environ.
        :type environment_variables: Dict[str, str]
        :param name: Name of the run.
        :type name: str
        :param display_name: Display name of the run.
        :type display_name: str
        :param tags: Tags of the run.
        :type tags: Dict[str, str]
        :return: Flow run info.
        :rtype: ~promptflow.entities.Run
        """
        if not os.path.exists(flow):
            raise FileNotFoundError(f"flow path {flow} does not exist")
        if data and not os.path.exists(data):
            raise FileNotFoundError(f"data path {data} does not exist")
        if not run and not data:
            raise ValueError("at least one of data or run must be provided")

        run = Run(
            name=name,
            display_name=display_name,
            tags=tags,
            data=data,
            column_mapping=column_mapping,
            run=run,
            variant=variant,
            flow=Path(flow),
            connections=connections,
            environment_variables=environment_variables,
        )
        return self.runs.create_or_update(run=run, **kwargs)

    def stream(self, run: Union[str, Run]) -> Run:
        """Stream run logs to the console.

        :param run: Run object or name of the run.
        :type run: Union[str, ~promptflow.sdk.entities.Run]
        :return: flow run info.
        :rtype: ~promptflow.sdk.entities.Run
        """
        return self.runs.stream(run)

    def get_details(
        self, run: Union[str, Run], max_results: int = MAX_SHOW_DETAILS_RESULTS, all_results: bool = False
    ) -> pd.DataFrame:
        """Get the details from the run including inputs and outputs.

        .. note::

            If `all_results` is set to True, `max_results` will be overwritten to sys.maxsize.

        :param run: The run name or run object
        :type run: Union[str, ~promptflow.sdk.entities.Run]
        :param max_results: The max number of runs to return, defaults to 100
        :type max_results: int
        :param all_results: Whether to return all results, defaults to False
        :type all_results: bool
        :raises RunOperationParameterError: If `max_results` is not a positive integer.
        :return: The details data frame.
        :rtype: pandas.DataFrame
        """
        return self.runs.get_details(name=run, max_results=max_results, all_results=all_results)

    def get_metrics(self, run: Union[str, Run]) -> Dict[str, Any]:
        """Get run metrics.

        :param run: Run object or name of the run.
        :type run: Union[str, ~promptflow.sdk.entities.Run]
        :return: Run metrics.
        :rtype: Dict[str, Any]
        """
        return self.runs.get_metrics(run)

    def visualize(self, runs: Union[List[str], List[Run]]) -> None:
        """Visualize run(s).

        :param run: Run object or name of the run.
        :type run: Union[str, ~promptflow.sdk.entities.Run]
        """
        self.runs.visualize(runs)

    @property
    def runs(self) -> RunOperations:
        """Run operations that can manage runs."""
        return self._runs

    @property
    def connections(self) -> ConnectionOperations:
        """Connection operations that can manage connections."""
        if not self._connections:
            if not self._connection_provider:
                self._connection_provider = Configuration.get_instance().get_connection_provider()
            if self._connection_provider == ConnectionProvider.LOCAL.value:
                logger.debug("Using local connection operations.")
                self._connections = ConnectionOperations()
            elif self._connection_provider.startswith(ConnectionProvider.AZUREML.value):
                logger.debug("Using local azure connection operations.")
                self._connections = LocalAzureConnectionOperations(self._connection_provider)
            else:
                raise ValueError(f"Unsupported connection provider: {self._connection_provider}")
        return self._connections

    @property
    def flows(self) -> FlowOperations:
        """Operations on the flow that can manage flows."""
        return self._flows

    def test(
        self,
        flow: Union[str, PathLike],
        *,
        inputs: dict = None,
        variant: str = None,
        node: str = None,
        environment_variables: dict = None,
    ) -> dict:
        """Test flow or node.

        :param flow: path to flow directory to test
        :type flow: Union[str, PathLike]
        :param inputs: Input data for the flow test
        :type inputs: dict
        :param variant: Node & variant name in format of ${node_name.variant_name}, will use default variant
            if not specified.
        :type variant: str
        :param node: If specified it will only test this node, else it will test the flow.
        :type node: str
        :param environment_variables: Environment variables to set by specifying a property path and value.
            Example: {"key1": "${my_connection.api_key}", "key2"="value2"}
            The value reference to connection keys will be resolved to the actual value,
            and all environment variables specified will be set into os.environ.
        :type environment_variables: dict
        :return: The result of flow or node
        :rtype: dict
        """
        return self.flows.test(
            flow=flow, inputs=inputs, variant=variant, environment_variables=environment_variables, node=node
        )

# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Union

from .._utils.logger_utils import get_cli_sdk_logger
from ._configuration import Configuration
from ._constants import MAX_SHOW_DETAILS_RESULTS
from ._load_functions import load_flow
from ._user_agent import USER_AGENT
from ._utils import ClientUserAgentUtil, get_connection_operation, setup_user_agent_to_operation_context
from .entities import Run
from .entities._eager_flow import EagerFlow
from .operations import RunOperations
from .operations._connection_operations import ConnectionOperations
from .operations._experiment_operations import ExperimentOperations
from .operations._flow_operations import FlowOperations
from .operations._tool_operations import ToolOperations
from .operations._trace_operations import TraceOperations

logger = get_cli_sdk_logger()


def _create_run(run: Run, **kwargs):
    client = PFClient()
    return client.runs.create_or_update(run=run, **kwargs)


class PFClient:
    """A client class to interact with prompt flow entities."""

    def __init__(self, **kwargs):
        logger.debug("PFClient init with kwargs: %s", kwargs)
        self._runs = RunOperations()
        self._connection_provider = kwargs.pop("connection_provider", None)
        self._config = kwargs.get("config", None) or {}
        # The credential is used as an option to override
        # DefaultAzureCredential when using workspace connection provider
        self._credential = kwargs.get("credential", None)
        # Lazy init to avoid azure credential requires too early
        self._connections = None
        self._flows = FlowOperations(client=self)
        self._tools = ToolOperations()
        # add user agent from kwargs if any
        if isinstance(kwargs.get("user_agent"), str):
            ClientUserAgentUtil.append_user_agent(kwargs["user_agent"])
        self._experiments = ExperimentOperations(self)
        self._traces = TraceOperations()
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
        # load flow object for validation and early failure
        flow_obj = load_flow(source=flow)
        # validate param conflicts
        if isinstance(flow_obj, EagerFlow):
            if variant or connections:
                logger.warning("variant and connections are not supported for eager flow, will be ignored")
                variant, connections = None, None
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
            config=Configuration(overrides=self._config),
        )
        return self.runs.create_or_update(run=run, **kwargs)

    def stream(self, run: Union[str, Run], raise_on_error: bool = True) -> Run:
        """Stream run logs to the console.

        :param run: Run object or name of the run.
        :type run: Union[str, ~promptflow.sdk.entities.Run]
        :param raise_on_error: Raises an exception if a run fails or canceled.
        :type raise_on_error: bool
        :return: flow run info.
        :rtype: ~promptflow.sdk.entities.Run
        """
        return self.runs.stream(run, raise_on_error)

    def get_details(
        self, run: Union[str, Run], max_results: int = MAX_SHOW_DETAILS_RESULTS, all_results: bool = False
    ) -> "DataFrame":
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
    def tools(self) -> ToolOperations:
        """Tool operations that can manage tools."""
        return self._tools

    def _ensure_connection_provider(self) -> str:
        if not self._connection_provider:
            # Get a copy with config override instead of the config instance
            self._connection_provider = Configuration(overrides=self._config).get_connection_provider()
            logger.debug("PFClient connection provider: %s", self._connection_provider)
        return self._connection_provider

    @property
    def connections(self) -> ConnectionOperations:
        """Connection operations that can manage connections."""
        if not self._connections:
            self._ensure_connection_provider()
            self._connections = get_connection_operation(self._connection_provider, self._credential)
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

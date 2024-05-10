# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import inspect
import json
import os
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from promptflow._constants import USER_AGENT_OVERRIDE_KEY, ConnectionProviderConfig, FlowLanguage
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.user_agent_utils import ClientUserAgentUtil, setup_user_agent_to_operation_context
from promptflow.exceptions import ErrorTarget, UserErrorException

from ._configuration import Configuration
from ._constants import MAX_SHOW_DETAILS_RESULTS
from ._load_functions import load_flow
from ._user_agent import USER_AGENT
from ._utilities.general_utils import generate_yaml_entry
from .entities import Run
from .entities._flows import FlexFlow, Prompty
from .entities._flows.base import FlowBase
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
        # when this is set, telemetry from this client will use this user agent and ignore the one from OperationContext
        self._user_agent_override = kwargs.pop(USER_AGENT_OVERRIDE_KEY, None)
        self._connection_provider = kwargs.pop("connection_provider", None)
        self._config = Configuration(overrides=kwargs.get("config", None) or {})
        # The credential is used as an option to override
        # DefaultAzureCredential when using workspace connection provider
        self._credential = kwargs.get("credential", None)

        # user_agent_override will be applied to all TelemetryMixin operations
        self._runs = RunOperations(self, user_agent_override=self._user_agent_override)
        self._flows = FlowOperations(client=self, user_agent_override=self._user_agent_override)
        self._experiments = ExperimentOperations(self, user_agent_override=self._user_agent_override)
        # Lazy init to avoid azure credential requires too early
        self._connections = None

        self._tools = ToolOperations()
        # add user agent from kwargs if any
        if isinstance(kwargs.get("user_agent"), str):
            ClientUserAgentUtil.append_user_agent(kwargs["user_agent"])
        self._traces = TraceOperations()
        setup_user_agent_to_operation_context(USER_AGENT)

    def _run(
        self,
        flow: Union[str, PathLike, Callable] = None,
        *,
        data: Union[str, PathLike] = None,
        run: Union[str, Run] = None,
        column_mapping: dict = None,
        variant: str = None,
        connections: dict = None,
        environment_variables: dict = None,
        properties: dict = None,
        name: str = None,
        display_name: str = None,
        tags: Dict[str, str] = None,
        resume_from: Union[str, Run] = None,
        code: Union[str, PathLike] = None,
        init: Optional[dict] = None,
        **kwargs,
    ) -> Run:
        """Run flow against provided data or run. Hide some parameters for internal use. Like "properties".

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
        :param properties: Additional properties to set for the run.
        :type properties: Dict[str, Any]
        :param name: Name of the run.
        :type name: str
        :param display_name: Display name of the run.
        :type display_name: str
        :param tags: Tags of the run.
        :type tags: Dict[str, str]
        :param resume_from: Create run resume from an existing run.
        :type resume_from: str
        :param code: Path to the code directory to run.
        :type code: Union[str, PathLike]
        :param init: Initialization parameters for flex flow, only supported when flow is callable class.
        :type init: dict
        :return: Flow run info.
        :rtype: ~promptflow.entities.Run
        """
        from promptflow._proxy import ProxyFactory

        if resume_from:
            unsupported = {
                k: v
                for k, v in {
                    "flow": flow,
                    "data": data,
                    "run": run,
                    "column_mapping": column_mapping,
                    "variant": variant,
                    "connections": connections,
                    "environment_variables": environment_variables,
                    "properties": properties,
                    "init": init,
                }.items()
                if v
            }
            if any(unsupported):
                raise ValueError(
                    f"'resume_from' is not supported to be used with the with following parameters: {unsupported}. "
                )
            resume_from = resume_from.name if isinstance(resume_from, Run) else resume_from
            return self.runs._create_by_resume_from(
                resume_from=resume_from, name=name, display_name=display_name, tags=tags, **kwargs
            )
        if not flow:
            raise ValueError("'flow' is required to create a run.")
        if callable(flow):
            logger.debug(f"flow entry {flow} is a callable.")
        elif ProxyFactory().get_executor_proxy_cls(FlowLanguage.Python).is_flex_flow_entry(entry=flow):
            logger.debug(f"flow entry {flow} is a python flex flow.")
        elif os.path.exists(flow):
            logger.debug(f"flow entry {flow} is a local path.")
        else:
            raise UserErrorException(f"Flow path {flow} does not exist and it's not a valid entry point.")
        if data and not os.path.exists(data):
            raise FileNotFoundError(f"data path {data} does not exist")
        if not run and not data:
            raise ValueError("at least one of data or run must be provided")

        is_flow_object = isinstance(flow, FlowBase)
        if callable(flow) and not inspect.isclass(flow) and not inspect.isfunction(flow):
            # The callable flow will be entry of flex flow or loaded prompty.
            if isinstance(flow, Prompty):
                # What is passed to the executor is the prompty in promptflow.core.
                dynamic_callable = flow._core_prompty
            else:
                dynamic_callable = flow
            if not is_flow_object:
                # For the entry of flex flow, getting the callable class to generate flex yaml.
                flow = flow.__class__
        else:
            dynamic_callable = None

        with generate_yaml_entry(entry=flow, code=code) as flow:
            if is_flow_object:
                flow_obj = flow
                flow_path = flow.path
            else:
                # load flow object for validation and early failure
                flow_obj = load_flow(source=flow)
                flow_path = Path(flow)
            # validate param conflicts
            if isinstance(flow_obj, (FlexFlow, Prompty)):
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
                flow=flow_path,
                connections=connections,
                environment_variables=environment_variables,
                properties=properties,
                config=self._config,
                init=init,
                dynamic_callable=dynamic_callable,
            )
            return self.runs.create_or_update(run=run, **kwargs)

    def run(
        self,
        flow: Union[str, PathLike, Callable] = None,
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
        resume_from: Union[str, Run] = None,
        code: Union[str, PathLike] = None,
        init: Optional[dict] = None,
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
        :param resume_from: Create run resume from an existing run.
        :type resume_from: str
        :param code: Path to the code directory to run.
        :type code: Union[str, PathLike]
        :param init: Initialization parameters for flex flow, only supported when flow is callable class.
        :type init: dict
        :return: Flow run info.
        :rtype: ~promptflow.entities.Run
        """
        return self._run(
            flow=flow,
            data=data,
            run=run,
            column_mapping=column_mapping,
            variant=variant,
            connections=connections,
            environment_variables=environment_variables,
            name=name,
            display_name=display_name,
            tags=tags,
            resume_from=resume_from,
            code=code,
            init=init,
            **kwargs,
        )

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
            self._connection_provider = self._config.get_connection_provider()
            logger.debug("PFClient connection provider: %s, setting to env.", self._connection_provider)
            from promptflow.core._connection_provider._connection_provider import ConnectionProvider

            # Set to os.environ for connection provider to use
            os.environ[ConnectionProvider.PROVIDER_CONFIG_KEY] = self._connection_provider
        return self._connection_provider

    @property
    def connections(self) -> ConnectionOperations:
        """Connection operations that can manage connections."""
        if not self._connections:
            self._ensure_connection_provider()
            self._connections = PFClient._build_connection_operation(
                self._connection_provider,
                self._credential,
                user_agent_override=self._user_agent_override,
            )
        return self._connections

    @staticmethod
    def _build_connection_operation(connection_provider: str, credential=None, **kwargs):
        """
        Build a ConnectionOperation object based on connection provider.

        :param connection_provider: Connection provider, e.g. local, azureml, azureml://subscriptions..., etc.
        :type connection_provider: str
        :param credential: Credential when remote provider, default to chained credential DefaultAzureCredential.
        :type credential: object
        """
        if connection_provider == ConnectionProviderConfig.LOCAL:
            from promptflow._sdk.operations._connection_operations import ConnectionOperations

            logger.debug("PFClient using local connection operations.")
            connection_operation = ConnectionOperations(**kwargs)
        elif connection_provider.startswith(ConnectionProviderConfig.AZUREML):
            from promptflow._sdk.operations._local_azure_connection_operations import LocalAzureConnectionOperations

            logger.debug(f"PFClient using local azure connection operations with credential {credential}.")
            connection_operation = LocalAzureConnectionOperations(connection_provider, credential=credential, **kwargs)
        else:
            raise UserErrorException(
                target=ErrorTarget.CONTROL_PLANE_SDK,
                message_format="Unsupported connection provider: {connection_provider}",
                connection_provider=connection_provider,
            )
        return connection_operation

    @property
    def flows(self) -> FlowOperations:
        """Operations on the flow that can manage flows."""
        return self._flows

    def test(
        self,
        flow: Union[str, PathLike],
        *,
        inputs: Union[dict, PathLike] = None,
        variant: str = None,
        node: str = None,
        environment_variables: dict = None,
        init: Optional[dict] = None,
    ) -> dict:
        """Test flow or node.

        :param flow: path to flow directory to test
        :type flow: Union[str, PathLike]
        :param inputs: Input data or json file for the flow test
        :type inputs: Union[dict, PathLike]
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
        :param init: Initialization parameters for flex flow, only supported when flow is callable class.
        :type init: dict
        :return: The result of flow or node
        :rtype: dict
        """
        # Load the inputs for the flow test from sample file.
        if isinstance(inputs, (str, Path)):
            if Path(inputs).suffix not in [".json", ".jsonl"]:
                raise UserErrorException("Only support jsonl or json file as input.")
            if not Path(inputs).exists():
                raise UserErrorException(f"Cannot find inputs file {inputs}.")
            if Path(inputs).suffix == ".json":
                with open(inputs, "r") as f:
                    inputs = json.load(f)
            else:
                from promptflow._utils.load_data import load_data

                inputs = load_data(local_path=inputs)[0]
        return self.flows.test(
            flow=flow, inputs=inputs, variant=variant, environment_variables=environment_variables, node=node, init=init
        )

    @property
    def traces(self) -> TraceOperations:
        """Operations on the trace that can manage traces."""
        return self._traces

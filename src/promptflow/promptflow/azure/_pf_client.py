# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
from os import PathLike
from pathlib import Path
from azure.ai.ml import MLClient
from typing import IO, AnyStr, List, Union, Dict, Any

from pandas import DataFrame

from promptflow._sdk.entities import Run
from promptflow.azure._load_functions import load_flow
from promptflow.azure._utils.gerneral import is_remote_uri
from promptflow._sdk._user_agent import USER_AGENT
from promptflow.azure.operations import RunOperations
from promptflow.azure.operations._flow_opearations import FlowOperations
from promptflow.azure.operations._connection_operations import ConnectionOperations


class PFClient:
    """A client class to interact with Promptflow service.

    Use this client to manage promptflow resources, e.g. runs

    :param ml_client: An instance of MLClient, indicates to interact with Promptflow service
    :type ml_client: azure.ai.ml.entities.MLClient
    :param kwargs: A dictionary of additional configuration parameters.
    :type kwargs: dict
    """

    def __init__(self, ml_client, **kwargs):
        if not isinstance(ml_client, MLClient):
            raise ValueError(
                f"ml_client must be an instance of 'azure.ai.MLClient', got {type(ml_client)!r} instead."
            )
        self._add_user_agent(kwargs)
        self._client = ml_client
        self._flows = FlowOperations(
            operation_scope=ml_client._operation_scope,
            operation_config=ml_client._operation_config,
            all_operations=ml_client._operation_container,
            credential=ml_client._credential,
            **kwargs,
        )
        self._runs = RunOperations(
            operation_scope=ml_client._operation_scope,
            operation_config=ml_client._operation_config,
            all_operations=ml_client._operation_container,
            credential=ml_client._credential,
            flow_operations=self._flows,
            **kwargs,
        )
        self._connections = ConnectionOperations(
            operation_scope=ml_client._operation_scope,
            operation_config=ml_client._operation_config,
            all_operations=ml_client._operation_container,
            credential=ml_client._credential,
            **kwargs,
        )

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
        Note: at least one of data or run must be provided.

        :param flow: path to flow directory to run evaluation
        :param data: pointer to test data (of variant bulk runs) for eval runs
        :param run:
            flow run id or flow run
            keep lineage between current run and variant runs
            batch outputs can be referenced as ${run.outputs.col_name} in inputs_mapping
        :param column_mapping: define a data flow logic to map input data, support:
            from data: data.col1:
            from run:
                run.inputs.col1: if need reference run's inputs
                run.output.col1: if need reference run's outputs
            Example:
                {"ground_truth": "${data.answer}", "prediction": "${run.outputs.answer}"}
        :param variant: Node & variant name in format of ${node_name.variant_name}, will use default variant
            if not specified.
        :param connections: Overwrite node level connections with provided value.
            Example: {"node1": {"connection": "new_connection", "deployment_name": "gpt-35-turbo"}}
        :param environment_variables: Environment variables to set by specifying a property path and value.
            Example: {"key1": "${my_connection.api_key}", "key2"="value2"}
            The value reference to connection keys will be resolved to the actual value,
            and all environment variables specified will be set into os.environ.
        :param name: Name of the run.
        :param display_name: Display name of the run.
        :param tags: Tags of the run.
        :return: flow run info.
        """
        if not os.path.exists(flow):
            raise FileNotFoundError(f"flow path {flow} does not exist")
        if is_remote_uri(data):
            # Pass through ARM id or remote url, the error will happen in runtime if format is not correct currently.
            pass
        else:
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
        """
        if isinstance(run, Run):
            run = run.name
        return self.runs.stream(run)

    def get_details(self, run: Union[str, Run]) -> DataFrame:
        """Preview run inputs and outputs.

        :param run: Run object or name of the run.
        :type run: Union[str, ~promptflow.sdk.entities.Run]
        :return: The run's details
        :rtype: pandas.DataFrame
        """
        if isinstance(run, Run):
            run = run.name
        return self.runs.get_details(run=run)

    def get_metrics(self, run: Union[str, Run]) -> dict:
        """Print run metrics to the console.

        :param run: Run object or name of the run.
        :type run: Union[str, ~promptflow.sdk.entities.Run]
        :return: The run's metrics
        :rtype: dict
        """
        if isinstance(run, Run):
            run = run.name
        return self.runs.get_metrics(run=run)

    def visualize(self, runs: Union[List[str], List[Run]]) -> None:
        """Visualize run(s).

        :param run: Run object or name of the run.
        :type run: Union[str, ~promptflow.sdk.entities.Run]
        """
        self.runs.visualize(runs)

    def load_as_component(
        self,
        source: Union[str, PathLike, IO[AnyStr]],
        *,
        component_type: str,
        columns_mapping: Dict[str, Union[str, float, int, bool]] = None,
        variant: str = None,
        environment_variables: Dict[str, Any] = None,
        is_deterministic: bool = True,
        **kwargs,
    ) -> "Component":
        """
        Load a flow as a component.
        :param source: Source of the flow. Should be a path to a flow dag yaml file or a flow directory.
        :type source: Union[str, PathLike, IO[AnyStr]]
        :param component_type: Type of the loaded component, support parallel only for now.
        :type component_type: str
        :param variant: Node variant used for the flow.
        :type variant: str
        :param environment_variables: Environment variables to set for the flow.
        :type environment_variables: dict
        :param columns_mapping: Inputs mapping for the flow.
        :type columns_mapping: dict
        :param is_deterministic: Whether the loaded component is deterministic.
        :type is_deterministic: bool
        """
        name = kwargs.pop("name", None)
        version = kwargs.pop("version", None)
        description = kwargs.pop("description", None)
        display_name = kwargs.pop("display_name", None)
        tags = kwargs.pop("tags", None)

        flow = load_flow(
            source=source,
            relative_origin=kwargs.pop("relative_origin", None),
            **kwargs,
        )

        if component_type != "parallel":
            raise NotImplementedError(
                f"Component type {component_type} is not supported yet."
            )

        # TODO: confirm if we should keep flow operations
        component = self._flows.load_as_component(
            flow=flow,
            columns_mapping=columns_mapping,
            variant=variant,
            environment_variables=environment_variables,
            name=name,
            version=version,
            description=description,
            is_deterministic=is_deterministic,
            display_name=display_name,
            tags=tags,
        )
        return component

    def _add_user_agent(self, kwargs) -> None:
        user_agent = kwargs.pop("user_agent", None)
        user_agent = f"{user_agent} {USER_AGENT}" if user_agent else USER_AGENT
        kwargs.setdefault("user_agent", user_agent)

    @property
    def runs(self):
        return self._runs

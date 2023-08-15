# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Union

import pandas as pd

from .entities import Run
from .operations import RunOperations
from .operations._connection_operations import ConnectionOperations
from .operations._flow_operations import FlowOperations


def _create_run(run: Run, **kwargs):
    client = PFClient()
    return client.runs.create_or_update(run=run, **kwargs)


class PFClient:
    """A client class to interact with prompt flow entities."""

    def __init__(self):
        self._runs = RunOperations()
        self._connections = ConnectionOperations()
        self._flows = FlowOperations()

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
        return self.runs.stream(run)

    def get_details(self, run: Union[str, Run]) -> pd.DataFrame:
        """Get run inputs and outputs.

        :param run: Run object or name of the run.
        :type run: Union[str, ~promptflow.sdk.entities.Run]
        :return: Run details.
        :rtype: ~pandas.DataFrame
        """
        return self.runs.get_details(run)

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
        return self._runs

    @property
    def connections(self) -> ConnectionOperations:
        return self._connections

    @property
    def flows(self) -> FlowOperations:
        """Operations on the flow, such as test/debug the flow, chat with chat flow."""
        return self._flows

    def test(
        self,
        flow: Union[str, PathLike],
        *,
        inputs: dict = None,
        variant: str = None,
        node: str = None,
        environment_variables: dict = None,
    ):
        """Test flow or node locally

        :param flow: path to flow directory to test
        :param inputs: Input data for the flow test
        :param variant: Node & variant name in format of ${node_name.variant_name}, will use default variant
            if not specified.
        :param node: If specified it will only test this node, else it will test the flow.
        :param environment_variables: Environment variables to set by specifying a property path and value.
            Example: {"key1": "${my_connection.api_key}", "key2"="value2"}
            The value reference to connection keys will be resolved to the actual value,
            and all environment variables specified will be set into os.environ.
        :return: The result of flow or node
        """
        return self.flows.test(
            flow=flow,
            inputs=inputs,
            variant=variant,
            environment_variables=environment_variables,
            node=node,
        )

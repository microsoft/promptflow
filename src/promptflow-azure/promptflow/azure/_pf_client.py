# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
from os import PathLike
from typing import Dict, List, Optional, Union

from azure.ai.ml import MLClient
from azure.core.credentials import TokenCredential

from promptflow._sdk._constants import MAX_SHOW_DETAILS_RESULTS
from promptflow._sdk._errors import RunOperationParameterError
from promptflow._sdk._utilities.general_utils import generate_yaml_entry
from promptflow._sdk.entities import Run
from promptflow._utils.user_agent_utils import ClientUserAgentUtil, setup_user_agent_to_operation_context
from promptflow.azure._restclient.service_caller_factory import _FlowServiceCallerFactory
from promptflow.azure.operations import RunOperations
from promptflow.azure.operations._arm_connection_operations import ArmConnectionOperations
from promptflow.azure.operations._connection_operations import ConnectionOperations
from promptflow.azure.operations._flow_operations import FlowOperations
from promptflow.azure.operations._trace_operations import TraceOperations
from promptflow.exceptions import UserErrorException

from ._user_agent import USER_AGENT


class PFClient:
    """A client class to interact with Promptflow service.

    Use this client to manage promptflow resources, e.g. runs.

    :param credential: Credential to use for authentication, optional
    :type credential: ~azure.core.credentials.TokenCredential
    :param subscription_id: Azure subscription ID, optional for registry assets only, optional
    :type subscription_id: typing.Optional[str]
    :param resource_group_name: Azure resource group, optional for registry assets only, optional
    :type resource_group_name: typing.Optional[str]
    :param workspace_name: Workspace to use in the client, optional for non workspace dependent operations only,
        optional.
    :type workspace_name: typing.Optional[str]
    :param kwargs: A dictionary of additional configuration parameters.
    :type kwargs: dict
    """

    def __init__(
        self,
        credential: TokenCredential = None,
        subscription_id: Optional[str] = None,
        resource_group_name: Optional[str] = None,
        workspace_name: Optional[str] = None,
        **kwargs,
    ):
        self._validate_config_information(subscription_id, resource_group_name, workspace_name, kwargs)
        # add user agent from kwargs if any
        if isinstance(kwargs.get("user_agent", None), str):
            ClientUserAgentUtil.append_user_agent(kwargs["user_agent"])
        # append SDK ua to context
        user_agent = setup_user_agent_to_operation_context(USER_AGENT)
        kwargs.setdefault("user_agent", user_agent)
        self._ml_client = kwargs.pop("ml_client", None) or MLClient(
            credential=credential,
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            **kwargs,
        )
        try:
            workspace = self._ml_client.workspaces.get(name=self._ml_client._operation_scope.workspace_name)
        except Exception as e:
            raise UserErrorException(message=str(e), error=e)
        self._service_caller = _FlowServiceCallerFactory.get_instance(
            workspace=workspace,
            credential=self._ml_client._credential,
            operation_scope=self._ml_client._operation_scope,
            **kwargs,
        )
        self._flows = FlowOperations(
            operation_scope=self._ml_client._operation_scope,
            operation_config=self._ml_client._operation_config,
            all_operations=self._ml_client._operation_container,
            credential=self._ml_client._credential,
            service_caller=self._service_caller,
            workspace=workspace,
            **kwargs,
        )
        self._traces = TraceOperations(
            operation_scope=self._ml_client._operation_scope,
            operation_config=self._ml_client._operation_config,
            service_caller=self._service_caller,
            **kwargs,
        )
        self._runs = RunOperations(
            operation_scope=self._ml_client._operation_scope,
            operation_config=self._ml_client._operation_config,
            all_operations=self._ml_client._operation_container,
            credential=self._ml_client._credential,
            flow_operations=self._flows,
            trace_operations=self._traces,
            service_caller=self._service_caller,
            workspace=workspace,
            **kwargs,
        )
        self._connections = ConnectionOperations(
            operation_scope=self._ml_client._operation_scope,
            operation_config=self._ml_client._operation_config,
            all_operations=self._ml_client._operation_container,
            credential=self._ml_client._credential,
            service_caller=self._service_caller,
            **kwargs,
        )
        self._arm_connections = ArmConnectionOperations(
            operation_scope=self._ml_client._operation_scope,
            operation_config=self._ml_client._operation_config,
            all_operations=self._ml_client._operation_container,
            credential=self._ml_client._credential,
            service_caller=self._service_caller,
            **kwargs,
        )

    @staticmethod
    def _validate_config_information(subscription_id, resource_group_name, workspace_name, kwargs):
        """Validate the config information in case wrong parameter name is passed into the constructor."""
        sub_name, wrong_sub_name = "subscription_id", "subscription"
        rg_name, wrong_rg_name = "resource_group_name", "resource_group"
        ws_name, wrong_ws_name = "workspace_name", "workspace"

        error_message = (
            "You have passed in the wrong parameter name to initialize the PFClient, please use {0!r} instead of {1!r}."
        )
        if not subscription_id and kwargs.get(wrong_sub_name, None) is not None:
            raise RunOperationParameterError(error_message.format(sub_name, wrong_sub_name))
        if not resource_group_name and kwargs.get(wrong_rg_name, None) is not None:
            raise RunOperationParameterError(error_message.format(rg_name, wrong_rg_name))
        if not workspace_name and kwargs.get(wrong_ws_name, None) is not None:
            raise RunOperationParameterError(error_message.format(ws_name, wrong_ws_name))

    @property
    def ml_client(self):
        """Return a client to interact with Azure ML services."""
        return self._ml_client

    @property
    def runs(self):
        """Return the run operation object that can manage runs."""
        return self._runs

    @property
    def flows(self):
        """Return the flow operation object that can manage flows."""
        return self._flows

    @classmethod
    def from_config(
        cls,
        credential: TokenCredential,
        *,
        path: Optional[Union[os.PathLike, str]] = None,
        file_name=None,
        **kwargs,
    ) -> "PFClient":
        """Return a PFClient object connected to Azure Machine Learning workspace.

        Reads workspace configuration from a file. Throws an exception if the config file can't be found.

        The method provides a simple way to reuse the same workspace across multiple Python notebooks or projects.
        Users can save the workspace Azure Resource Manager (ARM) properties using the
        [workspace.write_config](https://aka.ms/ml-workspace-class) method,
        and use this method to load the same workspace in different Python notebooks or projects without
        retyping the workspace ARM properties.

        :param credential: The credential object for the workspace.
        :type credential: ~azure.core.credentials.TokenCredential
        :param path: The path to the config file or starting directory to search.
            The parameter defaults to starting the search in the current directory.
            optional
        :type path: typing.Union[os.PathLike, str]
        :param file_name: Allows overriding the config file name to search for when path is a directory path.
            (Default value = None)
        :type file_name: str
        """

        ml_client = MLClient.from_config(credential=credential, path=path, file_name=file_name, **kwargs)
        return PFClient(
            ml_client=ml_client,
            **kwargs,
        )

    def run(
        self,
        flow: Union[str, PathLike] = None,
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

        .. note:: at least one of data or run must be provided.

        .. admonition::
            Data can be local file or remote path.
            - Example:
                - `data = "path/to/local/file"`
                - `data = "azureml:data_name:data_version"`
                - `data = "azureml://datastores/datastore_name/path/to/file"`
                - `data = "https://example.com/data.jsonl"`

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


        :param flow: path to flow directory to run evaluation
        :type flow: Union[str, PathLike]
        :param data: pointer to test data (of variant bulk runs) for eval runs
        :type data: Union[str, PathLike]
        :param run: flow run id or flow run, keep lineage between current run and variant runs,
            batch outputs can be referenced as ${run.outputs.col_name} in inputs_mapping
        :type run: Union[str, ~promptflow.entities.Run]
        :param column_mapping: define a data flow logic to map input data.
        :type column_mapping: dict
        :param variant: Node & variant name in format of ${node_name.variant_name}, will use default variant
            if not specified.
        :type variant: str
        :param connections: Overwrite node level connections with provided value.
            Example: ``{"node1": {"connection": "new_connection", "deployment_name": "gpt-35-turbo"}}``
        :type connections: dict
        :param environment_variables: Environment variables to set by specifying a property path and value.
            Example: ``{"key1": "${my_connection.api_key}", "key2"="value2"}``
            The value reference to connection keys will be resolved to the actual value,
            and all environment variables specified will be set into os.environ.
        :type environment_variables: dict
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
        :return: flow run info.
        :rtype: ~promptflow.entities.Run
        """
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
        if callable(flow):
            raise UserErrorException(f"Providing callable {flow} as flow is not supported.")
        with generate_yaml_entry(entry=flow, code=code) as flow:
            run = Run(
                name=name,
                display_name=display_name,
                tags=tags,
                data=data,
                column_mapping=column_mapping,
                run=run,
                variant=variant,
                flow=flow,
                connections=connections,
                environment_variables=environment_variables,
                init=init,
            )
            return self.runs.create_or_update(run=run, **kwargs)

    def stream(self, run: Union[str, Run], raise_on_error: bool = True) -> Run:
        """Stream run logs to the console.

        :param run: Run object or name of the run.
        :type run: Union[str, ~promptflow.sdk.entities.Run]
        :param raise_on_error: Raises an exception if a run fails or canceled.
        :type raise_on_error: bool
        :return: flow run info.
        """
        if isinstance(run, Run):
            run = run.name
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
        return self.runs.get_details(run=run, max_results=max_results, all_results=all_results)

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

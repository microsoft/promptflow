# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import concurrent
import copy
import hashlib
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from azure.ai.ml._artifacts._artifact_utilities import _upload_and_generate_remote_uri
from azure.ai.ml._scope_dependent_operations import (
    OperationConfig,
    OperationsContainer,
    OperationScope,
    _ScopeDependentOperations,
)
from azure.ai.ml.constants._common import AssetTypes, AzureMLResourceType
from azure.ai.ml.entities import Workspace
from azure.ai.ml.operations import DataOperations
from azure.ai.ml.operations._operation_orchestrator import OperationOrchestrator

from promptflow._constants import LANGUAGE_KEY, AzureWorkspaceKind, FlowLanguage
from promptflow._sdk._constants import (
    HOME_PROMPT_FLOW_DIR,
    LINE_NUMBER,
    MAX_RUN_LIST_RESULTS,
    MAX_SHOW_DETAILS_RESULTS,
    PROMPT_FLOW_RUNS_DIR_NAME,
    REGISTRY_URI_PREFIX,
    VIS_PORTAL_URL_TMPL,
    AzureRunTypes,
    IdentityKeys,
    ListViewType,
    RunDataKeys,
    RunHistoryKeys,
    RunStatus,
)
from promptflow._sdk._errors import InvalidRunStatusError, RunNotFoundError, RunOperationParameterError
from promptflow._sdk._telemetry import ActivityType, WorkspaceTelemetryMixin, monitor_operation
from promptflow._sdk._utilities.general_utils import (
    incremental_print,
    is_multi_container_enabled,
    is_remote_uri,
    print_red_error,
)
from promptflow._sdk.entities import Run
from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.utils import in_jupyter_notebook
from promptflow.azure._constants._flow import CLOUD_RUNS_PAGE_SIZE, COMPUTE_SESSION, COMPUTE_SESSION_NAME
from promptflow.azure._entities._trace import CosmosMetadata
from promptflow.azure._load_functions import load_flow
from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
from promptflow.azure._utils.general import get_authorization, get_user_alias_from_credential, set_event_loop_policy
from promptflow.azure.operations._flow_operations import FlowOperations
from promptflow.azure.operations._trace_operations import TraceOperations
from promptflow.exceptions import UserErrorException

RUNNING_STATUSES = RunStatus.get_running_statuses()

logger = get_cli_sdk_logger()


class RunRequestException(Exception):
    """RunRequestException."""

    def __init__(self, message):
        super().__init__(message)


class RunOperations(WorkspaceTelemetryMixin, _ScopeDependentOperations):
    """RunOperations that can manage runs.

    You should not instantiate this class directly. Instead, you should
    create an :class:`~promptflow.azure.PFClient` instance and this operation is available as the instance's attribute.
    """

    def __init__(
        self,
        operation_scope: OperationScope,
        operation_config: OperationConfig,
        all_operations: OperationsContainer,
        flow_operations: FlowOperations,
        trace_operations: TraceOperations,
        credential,
        service_caller: FlowServiceCaller,
        workspace: Workspace,
        **kwargs: Dict,
    ):
        super().__init__(
            operation_scope=operation_scope,
            operation_config=operation_config,
            workspace_name=operation_scope.workspace_name,
            subscription_id=operation_scope.subscription_id,
            resource_group_name=operation_scope.resource_group_name,
        )
        self._operation_scope = operation_scope
        self._all_operations = all_operations
        self._service_caller = service_caller
        self._workspace = workspace
        self._identity = workspace.identity
        self._credential = credential
        self._flow_operations = flow_operations
        self._trace_operations = trace_operations
        self._orchestrators = OperationOrchestrator(self._all_operations, self._operation_scope, self._operation_config)

    @property
    def _data_operations(self):
        return self._all_operations.get_operation(AzureMLResourceType.DATA, lambda x: isinstance(x, DataOperations))

    @property
    def _datastore_operations(self) -> "DatastoreOperations":
        return self._all_operations.all_operations[AzureMLResourceType.DATASTORE]

    @cached_property
    def _run_history_endpoint_url(self):
        """Get the endpoint url for the workspace."""
        endpoint = self._service_caller._service_endpoint
        return endpoint + "history/v1.0" + self._service_caller._common_azure_url_pattern

    @cached_property
    def _workspace_default_datastore(self):
        kind = self._workspace._kind
        # for a normal workspace the kind is "default", for an ai project it's "project". Except these two values, it
        # can also be "hub" which is not a supported workspace type to get default datastore.
        if kind not in [AzureWorkspaceKind.DEFAULT, AzureWorkspaceKind.PROJECT]:
            raise RunOperationParameterError(
                "Failed to get default workspace datastore. Please make sure you are using the right workspace which "
                f"is either an azure machine learning workspace or an azure ai project. Got {kind!r} instead."
            )
        return self._datastore_operations.get_default()

    def _get_run_portal_url(self, run_id: str):
        """Get the portal url for the run."""
        portal_url, run_info = None, None
        try:
            run_info = self._get_run_from_pfs(run_id=run_id)
        except Exception as e:
            logger.warning(f"Failed to get run portal url from pfs for run {run_id!r}: {str(e)}")

        if run_info and hasattr(run_info, "studio_portal_trace_endpoint"):
            portal_url = run_info.studio_portal_trace_endpoint

        return portal_url

    def _get_headers(self):
        custom_header = {
            "Authorization": get_authorization(credential=self._credential),
            "Content-Type": "application/json",
        }
        return custom_header

    @monitor_operation(activity_name="pfazure.runs.create_or_update", activity_type=ActivityType.PUBLICAPI)
    def create_or_update(self, run: Run, **kwargs) -> Run:
        """Create or update a run.

        :param run: Run object to create or update.
        :type run: ~promptflow.entities.Run
        :return: Run object created or updated.
        :rtype: ~promptflow.entities.Run
        """
        stream = kwargs.pop("stream", False)
        reset = kwargs.pop("reset_runtime", False)

        # validate the run object
        run._validate_for_run_create_operation()

        rest_obj = self._resolve_dependencies_in_parallel(run=run, runtime=kwargs.get("runtime"), reset=reset)

        self._service_caller.submit_bulk_run(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            body=rest_obj,
        )
        if in_jupyter_notebook():
            print(f"Portal url: {self._get_run_portal_url(run_id=run.name)}")
        if stream:
            self.stream(run=run.name)
        return self.get(run=run.name)

    @monitor_operation(activity_name="pfazure.runs.list", activity_type=ActivityType.PUBLICAPI)
    def list(
        self, max_results: int = MAX_RUN_LIST_RESULTS, list_view_type: ListViewType = ListViewType.ACTIVE_ONLY, **kwargs
    ) -> List[Run]:
        """List runs in the workspace.

        :param max_results: The max number of runs to return, defaults to 50, max is 100
        :type max_results: int
        :param list_view_type: The list view type, defaults to ListViewType.ACTIVE_ONLY
        :type list_view_type: ListViewType
        :return: The list of runs.
        :rtype: List[~promptflow.entities.Run]
        """
        if not isinstance(max_results, int) or max_results < 0:
            raise RunOperationParameterError(f"'max_results' must be a positive integer, got {max_results!r}")

        headers = self._get_headers()
        filter_archived = []
        if list_view_type == ListViewType.ACTIVE_ONLY:
            filter_archived = ["false"]
        elif list_view_type == ListViewType.ARCHIVED_ONLY:
            filter_archived = ["true"]
        elif list_view_type == ListViewType.ALL:
            filter_archived = ["true", "false"]
        else:
            raise RunOperationParameterError(
                f"Invalid list view type: {list_view_type!r}, expecting one of ['ActiveOnly', 'ArchivedOnly', 'All']"
            )

        pay_load = {
            "filters": [
                {"field": "type", "operator": "eq", "values": ["runs"]},
                {"field": "annotations/archived", "operator": "eq", "values": filter_archived},
                {
                    "field": "properties/runType",
                    "operator": "contains",
                    "values": [
                        AzureRunTypes.BATCH,
                        AzureRunTypes.EVALUATION,
                        AzureRunTypes.PAIRWISE_EVALUATE,
                    ],
                },
            ],
            "freeTextSearch": "",
            "order": [{"direction": "Desc", "field": "properties/creationContext/createdTime"}],
            # index service can return 100 results at most
            "pageSize": min(max_results, 100),
            "skip": 0,
            "includeTotalResultCount": True,
            "searchBuilder": "AppendPrefix",
        }

        endpoint = self._run_history_endpoint_url.replace("/history", "/index")
        url = endpoint + "/entities"
        response = requests.post(url, headers=headers, json=pay_load)

        if response.status_code == 200:
            entities = json.loads(response.text)
            runs = entities["value"]
        else:
            raise RunRequestException(
                f"Failed to get runs from service. Code: {response.status_code}, text: {response.text}"
            )
        refined_runs = []
        for run in runs:
            refined_runs.append(Run._from_index_service_entity(run))
        return refined_runs

    @monitor_operation(activity_name="pfazure.runs.get_metrics", activity_type=ActivityType.PUBLICAPI)
    def get_metrics(self, run: Union[str, Run], **kwargs) -> dict:
        """Get the metrics from the run.

        :param run: The run or the run object
        :type run: Union[str, ~promptflow.entities.Run]
        :return: The metrics
        :rtype: dict
        """
        run = Run._validate_and_return_run_name(run)
        self._check_cloud_run_completed(run_name=run)
        metrics = self._get_metrics_from_metric_service(run)
        return metrics

    @monitor_operation(activity_name="pfazure.runs.get_details", activity_type=ActivityType.PUBLICAPI)
    def get_details(
        self, run: Union[str, Run], max_results: int = MAX_SHOW_DETAILS_RESULTS, all_results: bool = False, **kwargs
    ) -> "DataFrame":
        """Get the details from the run.

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
        from pandas import DataFrame

        # if all_results is True, set max_results to sys.maxsize
        if all_results:
            max_results = sys.maxsize

        if not isinstance(max_results, int) or max_results < 1:
            raise RunOperationParameterError(f"'max_results' must be a positive integer, got {max_results!r}")

        run = Run._validate_and_return_run_name(run)
        self._check_cloud_run_completed(run_name=run)
        child_runs = self._get_flow_runs_pagination(run, max_results=max_results)
        inputs, outputs = self._get_inputs_outputs_from_child_runs(child_runs)

        # if there is any line run failed, the number of inputs and outputs will be different
        # this will result in pandas raising ValueError, so we need to handle mismatched case
        # if all line runs are failed, no need to fill the outputs
        if len(outputs) > 0:
            # get total number of line runs from inputs
            num_line_runs = len(list(inputs.values())[0])
            num_outputs = len(list(outputs.values())[0])
            if num_line_runs > num_outputs:
                # build full set with None as placeholder
                filled_outputs = {}
                output_keys = list(outputs.keys())
                for k in output_keys:
                    filled_outputs[k] = [None] * num_line_runs
                filled_outputs[LINE_NUMBER] = list(range(num_line_runs))
                for i in range(num_outputs):
                    line_number = outputs[LINE_NUMBER][i]
                    for k in output_keys:
                        filled_outputs[k][line_number] = outputs[k][i]
                # replace defective outputs with full set
                outputs = copy.deepcopy(filled_outputs)

        data = {}
        columns = []
        for k in inputs:
            new_k = f"inputs.{k}"
            data[new_k] = copy.deepcopy(inputs[k])
            columns.append(new_k)
        for k in outputs:
            new_k = f"outputs.{k}"
            data[new_k] = copy.deepcopy(outputs[k])
            columns.append(new_k)
        df = DataFrame(data).reindex(columns=columns)
        if f"outputs.{LINE_NUMBER}" in columns:
            df = df.set_index(f"outputs.{LINE_NUMBER}")
        return df

    def _check_cloud_run_completed(self, run_name: str) -> bool:
        """Check if the cloud run is completed."""
        run = self.get(run=run_name)
        run._check_run_status_is_completed()

    def _get_flow_runs_pagination(self, name: str, max_results: int) -> List[dict]:
        # call childRuns API with pagination to avoid PFS OOM
        # different from UX, run status should be completed here
        flow_runs = []
        start_index, end_index = 0, CLOUD_RUNS_PAGE_SIZE - 1
        while start_index < max_results:
            current_flow_runs = self._service_caller.get_child_runs(
                subscription_id=self._operation_scope.subscription_id,
                resource_group_name=self._operation_scope.resource_group_name,
                workspace_name=self._operation_scope.workspace_name,
                flow_run_id=name,
                start_index=start_index,
                end_index=end_index,
            )
            # no data in current page
            if len(current_flow_runs) == 0:
                break
            start_index, end_index = start_index + CLOUD_RUNS_PAGE_SIZE, end_index + CLOUD_RUNS_PAGE_SIZE
            flow_runs += current_flow_runs
        return flow_runs[0:max_results]

    def _extract_metrics_from_metric_service_response(self, values) -> dict:
        """Get metrics from the metric service response."""
        refined_metrics = {}
        metric_list = values.get("value", [])
        if not metric_list:
            return refined_metrics

        for metric in metric_list:
            metric_name = metric["name"]
            if self._is_system_metric(metric_name):
                continue
            refined_metrics[metric_name] = metric["value"][0]["data"][metric_name]
        return refined_metrics

    def _get_metrics_from_metric_service(self, run_id) -> dict:
        """Get the metrics from metric service."""
        headers = self._get_headers()
        # refer to MetricController: https://msdata.visualstudio.com/Vienna/_git/vienna?path=/src/azureml-api/src/Metric/EntryPoints/Api/Controllers/MetricController.cs&version=GBmaster  # noqa: E501
        endpoint = self._run_history_endpoint_url.replace("/history/v1.0", "/metric/v2.0")
        url = endpoint + f"/runs/{run_id}/lastvalues"
        response = requests.post(url, headers=headers, json={})
        if response.status_code == 200:
            values = response.json()
            return self._extract_metrics_from_metric_service_response(values)
        else:
            raise RunRequestException(
                f"Failed to get metrics from service. Code: {response.status_code}, text: {response.text}"
            )

    @staticmethod
    def _is_system_metric(metric: str) -> bool:
        """Check if the metric is system metric.

        Current we have some system metrics like: __pf__.lines.completed, __pf__.lines.bypassed,
        __pf__.lines.failed, __pf__.nodes.xx.completed
        """
        return (
            metric.endswith(".completed")
            or metric.endswith(".bypassed")
            or metric.endswith(".failed")
            or metric.endswith(".is_completed")
        )

    @monitor_operation(activity_name="pfazure.runs.get", activity_type=ActivityType.PUBLICAPI)
    def get(self, run: Union[str, Run], **kwargs) -> Run:
        """Get a run.

        :param run: The run name
        :type run: Union[str, ~promptflow.entities.Run]
        :return: The run object
        :rtype: ~promptflow.entities.Run
        """
        run = Run._validate_and_return_run_name(run)
        return self._get_run_from_run_history(flow_run_id=run, **kwargs)

    def _get_run_from_run_history(self, flow_run_id, original_form=False, **kwargs):
        """Get run info from run history"""
        headers = self._get_headers()
        url = self._run_history_endpoint_url + "/rundata"

        payload = {
            "runId": flow_run_id,
            "selectRunMetadata": True,
            "selectRunDefinition": True,
            "selectJobSpecification": True,
        }

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            run = response.json()
            # if original_form is True, return the original run data from run history, mainly for test use
            if original_form:
                return run
            run_data = self._refine_run_data_from_run_history(run)
            run = Run._from_run_history_entity(run_data)
            return run
        elif response.status_code == 404:
            raise RunNotFoundError(f"Run {flow_run_id!r} not found.")
        else:
            raise RunRequestException(
                f"Failed to get run from service. Code: {response.status_code}, text: {response.text}"
            )

    def _refine_run_data_from_run_history(self, run_data: dict) -> dict:
        """Refine the run data from run history.

        Generate the portal url, input and output value from run history data.
        """
        run_data = run_data[RunHistoryKeys.RunMetaData]
        # add cloud run url
        run_data[RunDataKeys.PORTAL_URL] = self._get_run_portal_url(run_id=run_data["runId"])

        # get input and output value
        # TODO: Unify below values to the same pattern - azureml://xx
        properties = run_data["properties"]
        input_data = properties.pop("azureml.promptflow.input_data", None)
        input_run_id = properties.pop("azureml.promptflow.input_run_id", None)
        output_data = run_data["outputs"]
        if output_data:
            output_data = output_data.get("flow_outputs", {}).get("assetId", None)
        run_data[RunDataKeys.DATA] = input_data
        run_data[RunDataKeys.RUN] = input_run_id
        run_data[RunDataKeys.OUTPUT] = output_data

        return run_data

    def _get_run_from_index_service(self, flow_run_id, **kwargs):
        """Get run info from index service"""
        headers = self._get_headers()
        payload = {
            "filters": [
                {"field": "type", "operator": "eq", "values": ["runs"]},
                {"field": "annotations/archived", "operator": "eq", "values": ["false"]},
                {"field": "properties/runId", "operator": "eq", "values": [flow_run_id]},
            ],
            "order": [{"direction": "Desc", "field": "properties/startTime"}],
            "pageSize": 50,
        }
        endpoint = self._run_history_endpoint_url.replace("/history", "/index")
        url = endpoint + "/entities"
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            runs = response.json().get("value", None)
            if not runs:
                raise RunRequestException(
                    f"Could not found run with run id {flow_run_id!r}, please double check the run id and try again."
                )
            run = runs[0]
            return Run._from_index_service_entity(run)
        else:
            raise RunRequestException(
                f"Failed to get run metrics from service. Code: {response.status_code}, text: {response.text}"
            )

    def _get_run_from_pfs(self, run_id, **kwargs):
        """Get run info from pfs"""
        return self._service_caller.get_flow_run(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            flow_run_id=run_id,
        )

    @monitor_operation(activity_name="pfazure.runs.archive", activity_type=ActivityType.PUBLICAPI)
    def archive(self, run: Union[str, Run]) -> Run:
        """Archive a run.

        :param run: The run name or run object
        :type run: Union[str, ~promptflow.entities.Run]
        :return: The run object
        :rtype: ~promptflow.entities.Run
        """

        run = Run._validate_and_return_run_name(run)
        payload = {
            RunHistoryKeys.HIDDEN: True,
        }
        return self._modify_run_in_run_history(run_id=run, payload=payload)

    @monitor_operation(activity_name="pfazure.runs.restore", activity_type=ActivityType.PUBLICAPI)
    def restore(self, run: Union[str, Run]) -> Run:
        """Restore a run.

        :param run: The run name or run object
        :type run: Union[str, ~promptflow.entities.Run]
        :return: The run object
        :rtype: ~promptflow.entities.Run
        """
        run = Run._validate_and_return_run_name(run)
        payload = {
            RunHistoryKeys.HIDDEN: False,
        }
        return self._modify_run_in_run_history(run_id=run, payload=payload)

    def _get_log(self, flow_run_id: str) -> str:
        """Get logs for a flow run with retry for the case when logs are being created.

        :param flow_run_id: The flow run ID.
        :type flow_run_id: str
        :return: The log content.
        :rtype: str
        """
        from azure.core.exceptions import HttpResponseError
        from functools import wraps
        import time
        
        # Define a retry decorator specifically for this operation
        def retry_get_log(max_tries=5, initial_delay=1, backoff=2):
            def deco_retry(f):
                @wraps(f)
                def f_retry(*args, **kwargs):
                    tries_remaining, delay_seconds = max_tries, initial_delay
                    while tries_remaining > 1:
                        try:
                            return f(*args, **kwargs)
                        except HttpResponseError as e:
                            # Only retry on 400 errors with the specific message
                            if e.status_code == 400 and "Value cannot be null. (Parameter 'bytes')" in str(e):
                                time.sleep(delay_seconds)
                                tries_remaining -= 1
                                delay_seconds *= backoff
                                logger.warning(
                                    "Log file is still being created. Retrying in %d seconds... (%d tries left)",
                                    delay_seconds, tries_remaining
                                )
                            else:
                                # For other errors, just raise
                                raise
                    return f(*args, **kwargs)
                return f_retry
            return deco_retry

        # Apply the retry decorator to the get_flow_run_log_content call
        @retry_get_log()
        def get_log_with_retry():
            return self._service_caller.caller.bulk_runs.get_flow_run_log_content(
                subscription_id=self._operation_scope.subscription_id,
                resource_group_name=self._operation_scope.resource_group_name,
                workspace_name=self._operation_scope.workspace_name,
                flow_run_id=flow_run_id,
                headers=self._get_headers(),
            )

        return get_log_with_retry()

    @monitor_operation(activity_name="pfazure.runs.update", activity_type=ActivityType.PUBLICAPI)
    def update(
        self,
        run: Union[str, Run],
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Optional[Run]:
        """Update a run. May update the display name, description or tags.

        .. note::

            - Display name and description are strings, and tags is a dictionary of key-value pairs, both key and value
              are also strings.
            - Tags is a dictionary of key-value pairs. Updating tags will overwrite the existing key-value pair,
              but will not delete the existing key-value pairs.

        :param run: The run name or run object
        :type run: Union[str, ~promptflow.entities.Run]
        :param display_name: The display name
        :type display_name: Optional[str]
        :param description: The description
        :type description: Optional[str]
        :param tags: The tags
        :type tags: Optional[Dict[str, str]]
        :raises UpdateRunError: If nothing or wrong type values provided to update the run.
        :return: The run object
        :rtype: Optional[~promptflow.entities.Run]
        """
        run = Run._validate_and_return_run_name(run)
        if display_name is None and description is None and tags is None:
            logger.warning("Nothing provided to update the run.")
            return None

        payload = {}

        if isinstance(display_name, str):
            payload["displayName"] = display_name
        elif display_name is not None:
            logger.warning(f"Display name must be a string, got {type(display_name)!r}: {display_name!r}.")

        if isinstance(description, str):
            payload["description"] = description
        elif description is not None:
            logger.warning(f"Description must be a string, got {type(description)!r}: {description!r}.")

        # check if the tags type is Dict[str, str]
        if isinstance(tags, dict) and all(
            isinstance(key, str) and isinstance(value, str) for key, value in tags.items()
        ):
            payload["tags"] = tags
        elif tags is not None:
            logger.warning(f"Tags type must be 'Dict[str, str]', got non-dict or non-string key/value in tags: {tags}.")

        return self._modify_run_in_run_history(run_id=run, payload=payload)

    @monitor_operation(activity_name="pfazure.runs.stream", activity_type=ActivityType.PUBLICAPI)
    def stream(self, run: Union[str, Run], raise_on_error: bool = True, timeout: int = 600, **kwargs) -> Run:
        """Stream the logs of a run.

        :param run: The run name or run object
        :type run: Union[str, ~promptflow.entities.Run]
        :param timeout: If the run stays in the same status and produce no new logs in a period
             longer than the timeout value, the stream operation will abort. Default timeout value is 600 seconds.
        :type timeout: int
        :param raise_on_error: Raises an exception if a run fails or canceled.
        :type raise_on_error: bool
        :return: The run object
        :rtype: ~promptflow.entities.Run
        """
        run = self.get(run=run)
        # TODO: maybe we need to make this configurable
        file_handler = sys.stdout
        # different from Azure ML job, flow job can run very fast, so it might not print anything;
        # use below variable to track this behavior, and at least print something to the user.
        try:
            printed = 0
            stream_count = 0
            prev_active_time = time.time()
            prev_active_log = ""
            prev_active_status = run.status

            while run.status in RUNNING_STATUSES or run.status == RunStatus.FINALIZING:
                file_handler.flush()
                stream_count += 1
                # print prompt every 3 times, in case there is no log printed
                if stream_count % 3 == 0:
                    # print prompt every 3 times
                    file_handler.write(f"(Run status is {run.status!r}, continue streaming...)\n")

                available_logs = self._get_log(flow_run_id=run.name)
                printed = incremental_print(available_logs, printed, file_handler)

                # if the run status is not changed, and the log is not changed, and it lasts for timeout seconds,
                # we assume the run is stuck, and we should stop the streaming.
                if available_logs != prev_active_log or run.status != prev_active_status:
                    prev_active_log = available_logs
                    prev_active_status = run.status
                    prev_active_time = time.time()
                elif time.time() - prev_active_time > timeout:
                    file_handler.write(
                        f"The run {run.name!r} is in status {run.status} and produce no new logs for {timeout} seconds,"
                        "streaming is stopped. If the final status is 'NotStarted', "
                        "Please make sure you are using the latest session.\n"
                        f"For {COMPUTE_SESSION} case, please try extending the timeout value.\n"
                    )
                    break

                time.sleep(10)
                run = self.get(run=run.name)
            # ensure all logs are printed
            file_handler.flush()
            available_logs = self._get_log(flow_run_id=run.name)
            incremental_print(available_logs, printed, file_handler)

            file_handler.write("======= Run Summary =======\n")
            duration = None
            if run._start_time and run._end_time:
                duration = str(run._end_time - run._start_time)
            file_handler.write(
                f'Run name: "{run.name}"\n'
                f'Run status: "{run.status}"\n'
                f'Start time: "{run._start_time}"\n'
                f'Duration: "{duration}"\n'
                f'Run url: "{self._get_run_portal_url(run_id=run.name)}"'
            )
        except KeyboardInterrupt:
            error_message = (
                "The output streaming for the flow run was interrupted.\n"
                "But the run is still executing on the cloud.\n"
            )
            print(error_message)

        if run.status == RunStatus.FAILED or run.status == RunStatus.CANCELED:
            if run.status == RunStatus.FAILED:
                try:
                    error_message = run._error["error"]["message"]
                except Exception:  # pylint: disable=broad-except
                    error_message = "Run fails with unknown error."
            else:
                error_message = "Run is canceled."
            if raise_on_error:
                raise InvalidRunStatusError(error_message)
            else:
                print_red_error(error_message)

        return run

    def _resolve_data_to_asset_id(self, run: Run):
        # Skip if no data provided
        if run.data is None:
            return
        test_data = run.data

        def _get_data_type(_data):
            if os.path.isdir(_data):
                return AssetTypes.URI_FOLDER
            else:
                return AssetTypes.URI_FILE

        if is_remote_uri(test_data):
            # Pass through ARM id or remote url
            return test_data

        if os.path.exists(test_data):  # absolute local path, upload, transform to remote url
            data_type = _get_data_type(test_data)
            test_data = _upload_and_generate_remote_uri(
                self._operation_scope,
                self._datastore_operations,
                test_data,
                datastore_name=self._workspace_default_datastore.name,
                show_progress=self._show_progress,
            )
            if data_type == AssetTypes.URI_FOLDER and test_data and not test_data.endswith("/"):
                test_data = test_data + "/"
        else:
            raise ValueError(
                f"Local path {test_data!r} not exist. "
                "If it's remote data, only data with azureml prefix or remote url is supported."
            )
        return test_data

    def _resolve_flow_and_session_id(self, run: Run) -> Tuple[str, Optional[str]]:
        """Resolve flow to remote flow and session id."""
        # for remote flow case, leave session id to None and let service side resolve
        if run._use_remote_flow:
            return self._resolve_flow_definition_resource_id(run=run), None

        flow = load_flow(run.flow)
        # set init kwargs for validation
        flow._init_kwargs = run.init
        self._flow_operations._resolve_arm_id_or_upload_dependencies(
            flow=flow,
            # ignore .promptflow/dag.tools.json only for run submission scenario in python
            ignore_tools_json=flow._flow_dict.get(LANGUAGE_KEY, None) != FlowLanguage.CSharp,
        )
        # for local flow case, use flow path to calculate session id
        session_id = self._get_session_id(flow=flow, flow_lineage_id=run._lineage_id)
        return flow.path, session_id

    def _get_session_id(self, flow, flow_lineage_id):
        try:
            user_alias = get_user_alias_from_credential(self._credential)
        except Exception:
            # fall back to unknown user when failed to get credential.
            user_alias = "unknown_user"
        # for different environment, use different session id to avoid image cache
        env = flow._environment
        env_hash = hashlib.sha256(json.dumps(env, sort_keys=True).encode()).hexdigest()
        session_id = f"{user_alias}_{flow_lineage_id}_{env_hash}"
        # hash and truncate to avoid the session id getting too long
        # backend has a 64 bit limit for session id.
        # use hexdigest to avoid non-ascii characters in session id
        session_id = str(hashlib.sha256(session_id.encode()).hexdigest())[:48]
        return session_id

    def _get_inputs_outputs_from_child_runs(self, runs: List[Dict[str, Any]]):
        """Get the inputs and outputs from the child runs."""
        inputs = {}
        outputs = {}
        outputs[LINE_NUMBER] = []
        runs.sort(key=lambda x: x["index"])
        # 1st loop, until have all outputs keys
        outputs_keys = []
        for run in runs:
            run_outputs = run["output"]
            if isinstance(run_outputs, dict):
                for k in run_outputs:
                    outputs_keys.append(k)
                break
        # 2nd complete loop, get values
        for run in runs:
            index, run_inputs, run_outputs = run["index"], run["inputs"], run["output"]
            # input should always available as a dict
            for k, v in run_inputs.items():
                if k not in inputs:
                    inputs[k] = []
                inputs[k].append(v)
            # output
            outputs[LINE_NUMBER].append(index)
            # for failed line run, output is None, instead of a dict
            # in this case, we append an empty line
            if not isinstance(run_outputs, dict):
                for k in outputs_keys:
                    if k == LINE_NUMBER:
                        continue
                    if k not in outputs:
                        outputs[k] = []
                    outputs[k].append(None)
            else:
                for k, v in run_outputs.items():
                    if k not in outputs:
                        outputs[k] = []
                    outputs[k].append(v)
        return inputs, outputs

    @monitor_operation(activity_name="pfazure.runs.visualize", activity_type=ActivityType.PUBLICAPI)
    def visualize(self, runs: Union[str, Run, List[str], List[Run]], **kwargs) -> None:
        """Visualize run(s) using Azure AI portal.

        :param runs: Names of the runs, or list of run objects.
        :type runs: Union[str, ~promptflow.sdk.entities.Run, List[str], List[~promptflow.sdk.entities.Run]]
        """
        if not isinstance(runs, list):
            runs = [runs]

        validated_runs = []
        for run in runs:
            run_name = Run._validate_and_return_run_name(run)
            validated_runs.append(run_name)

        subscription_id = self._operation_scope.subscription_id
        resource_group_name = self._operation_scope.resource_group_name
        workspace_name = self._operation_scope.workspace_name
        names = ",".join(validated_runs)
        portal_url = VIS_PORTAL_URL_TMPL.format(
            subscription_id=subscription_id,
            resource_group_name=resource_group_name,
            workspace_name=workspace_name,
            names=names,
        )
        print(f"Web View: {portal_url}")

    @classmethod
    def _resolve_automatic_runtime(cls):
        logger.warning(
            f"You're using {COMPUTE_SESSION}, if it's first time you're using it, "
            "it may take a while to build session and you may see 'NotStarted' status for a while. "
        )
        runtime_name = COMPUTE_SESSION_NAME
        return runtime_name

    def _resolve_runtime(self, run, runtime):
        runtime = run._runtime or runtime

        if runtime is None or runtime == COMPUTE_SESSION_NAME:
            runtime = self._resolve_automatic_runtime()
        elif not isinstance(runtime, str):
            raise TypeError(f"runtime should be a string, got {type(runtime)} for {runtime}")
        return runtime

    def _get_cosmos_metadata(self) -> CosmosMetadata:
        return self._trace_operations._get_cosmos_metadata()

    def _resolve_dependencies_in_parallel(self, run: Run, runtime, reset=None):
        # local import to avoid circular import related to PFClient
        from promptflow.azure._utils._tracing import resolve_disable_trace

        with ThreadPoolExecutor() as pool:
            tasks = [
                pool.submit(self._resolve_data_to_asset_id, run=run),
                pool.submit(self._resolve_flow_and_session_id, run=run),
                pool.submit(self._get_cosmos_metadata),
            ]
            concurrent.futures.wait(tasks, return_when=concurrent.futures.ALL_COMPLETED)
            task_results = [task.result() for task in tasks]

        run.data = task_results[0]
        run.flow, session_id = task_results[1]
        cosmos_metadata = task_results[2]

        runtime = self._resolve_runtime(run=run, runtime=runtime)
        self._resolve_identity(run=run)

        rest_obj = run._to_rest_object()
        rest_obj.runtime_name = runtime
        rest_obj.session_id = session_id
        rest_obj.disable_trace = resolve_disable_trace(metadata=cosmos_metadata, logger=logger)

        # TODO(2884482): support force reset & force install

        if runtime == "None":
            # HARD CODE for office scenario, use workspace default runtime when specified None
            rest_obj.runtime_name = None

        return rest_obj

    def _refine_payload_for_run_update(self, payload: dict, key: str, value, expected_type: type) -> dict:
        """Refine the payload for run update."""
        if value is not None:
            payload[key] = value
        return payload

    def _modify_run_in_run_history(self, run_id: str, payload: dict) -> Run:
        """Modify run info in run history."""
        headers = self._get_headers()
        url = self._run_history_endpoint_url + f"/runs/{run_id}/modify"

        response = requests.patch(url, headers=headers, json=payload)

        if response.status_code == 200:
            # the modify api returns different data format compared with get api, so we use get api here to
            # return standard Run object
            return self.get(run=run_id)
        else:
            raise RunRequestException(
                f"Failed to modify run in run history. Code: {response.status_code}, text: {response.text}"
            )

    def _resolve_flow_definition_resource_id(self, run: Run):
        """Resolve the flow definition resource id."""
        # for registry flow pattern, the flow uri can be passed as flow definition resource id directly
        if run.flow.startswith(REGISTRY_URI_PREFIX):
            return run.flow

        # for workspace flow pattern, generate the flow definition resource id
        workspace_id = self._workspace._workspace_id
        location = self._workspace.location
        return f"azureml://locations/{location}/workspaces/{workspace_id}/flows/{run._flow_name}"

    @monitor_operation(activity_name="pfazure.runs.download", activity_type=ActivityType.PUBLICAPI)
    def download(
        self, run: Union[str, Run], output: Optional[Union[str, Path]] = None, overwrite: Optional[bool] = False
    ) -> str:
        """Download the data of a run, including input, output, snapshot and other run information.

        .. note::

            After the download is finished, you can use ``pf run create --source <run-info-local-folder>``
            to register this run as a local run record, then you can use commands like ``pf run show/visualize``
            to inspect the run just like a run that was created from local flow.

        :param run: The run name or run object
        :type run: Union[str, ~promptflow.entities.Run]
        :param output: The output directory. Default to be default to be "~/.promptflow/.runs" folder.
        :type output: Optional[str]
        :param overwrite: Whether to overwrite the existing run folder. Default to be False.
        :type overwrite: Optional[bool]
        :return: The run directory path
        :rtype: str
        """
        from promptflow.azure.operations._async_run_downloader import AsyncRunDownloader

        run = Run._validate_and_return_run_name(run)
        run_folder = self._validate_for_run_download(run=run, output=output, overwrite=overwrite)
        run_downloader = AsyncRunDownloader._from_run_operations(run_ops=self, run=run, output_folder=run_folder)
        set_event_loop_policy()
        async_run_allowing_running_loop(run_downloader.download)
        result_path = run_folder.resolve().as_posix()
        logger.info(f"Successfully downloaded run {run!r} to {result_path!r}.")
        return result_path

    @monitor_operation(activity_name="pfazure.runs.upload", activity_type=ActivityType.PUBLICAPI)
    def _upload(self, run: Optional[Union[str, Run]], run_uploader=None) -> str:
        from promptflow.azure.operations._async_run_uploader import AsyncRunUploader

        set_event_loop_policy()

        # if the run_uploader is not provided, create a new one
        if run_uploader is None:
            run_uploader = AsyncRunUploader._from_run_operations(run_ops=self)

        # upload local run details to cloud
        result_dict = async_run_allowing_running_loop(run_uploader.upload, run=run)
        run = run_uploader.run
        # patch details about the uploaded run
        run._local_to_cloud_info = result_dict
        logger.debug(f"Successfully uploaded run details of {run.name!r} to cloud.")

        # registry the run in the cloud
        self._register_existing_bulk_run(run=run)

        # post process after run upload, it can only be done after the run history record is created
        async_run_allowing_running_loop(run_uploader.post_process)
        logger.debug(f"Successfully post processed run {run.name!r} after upload.")

        portal_url = self._get_run_portal_url(run_id=run.name)
        # print portal url when executing in jupyter notebook
        if in_jupyter_notebook():
            print(f"Portal url: {portal_url}")

        return portal_url

    def _register_existing_bulk_run(self, run: Run):
        """Register the run in the cloud"""
        rest_obj = run._to_rest_object()
        self._service_caller.create_existing_bulk_run(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            body=rest_obj,
        )
        logger.info(f"Successfully registered run {run.name!r} to cloud.")

    def _validate_for_run_download(self, run: Union[str, Run], output: Optional[Union[str, Path]], overwrite):
        """Validate the run download parameters."""
        run = Run._validate_and_return_run_name(run)

        # process the output path
        if output is None:
            # default to be "~/.promptflow/.runs" folder
            output_directory = HOME_PROMPT_FLOW_DIR / PROMPT_FLOW_RUNS_DIR_NAME
        else:
            output_directory = Path(output)

        # validate the run folder
        run_folder = output_directory / run
        if run_folder.exists():
            if overwrite is True:
                logger.warning("Removing existing run folder %r.", run_folder.resolve().as_posix())
                shutil.rmtree(run_folder)
            else:
                raise UserErrorException(
                    f"Run folder {run_folder.resolve().as_posix()!r} already exists, please specify a new output path "
                    f"or set the overwrite flag to be true."
                )

        # check the run status, only download the completed run
        run = self.get(run=run)
        if run.status != RunStatus.COMPLETED:
            raise UserErrorException(
                f"Can only download the run with status {RunStatus.COMPLETED!r} "
                f"while {run.name!r}'s status is {run.status!r}."
            )

        run_folder.mkdir(parents=True)
        return run_folder

    @monitor_operation(activity_name="pfazure.runs.cancel", activity_type=ActivityType.PUBLICAPI)
    def cancel(self, run: Union[str, Run], **kwargs) -> None:
        """Cancel a run.

        :param run: The run name or run object
        :type run: Union[str, ~promptflow.entities.Run]
        """
        run = Run._validate_and_return_run_name(run)
        self._service_caller.cancel_flow_run(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            flow_run_id=run,
        )

    def _build_resume_request_rest_object(
        self,
        name: str = None,
        display_name: str = None,
        description: str = None,
        tags: Dict[str, str] = None,
        resume_from: str = None,
        resources: Dict[str, Any] = None,
        identity: str = None,
        **kwargs,
    ):
        """Build the resume request rest object."""
        if kwargs:
            logger.warning(f"Unrecognized parameters {kwargs!r} are ignored.")
        resources = resources or {}
        from promptflow.azure._restclient.flow.models import ResumeBulkRunRequest

        rest_obj = ResumeBulkRunRequest(
            run_id=name,
            run_display_name=display_name,
            description=description,
            tags=tags,
            resume_from_run_id=resume_from,
            runtime_name=resources.get("runtime"),
            vm_size=resources.get("instance_type"),
            identity=identity,
            compute_name=resources.get("compute"),
            enable_multi_container=is_multi_container_enabled(),
        )
        return rest_obj

    @monitor_operation(activity_name="pfazure.runs.resume", activity_type=ActivityType.PUBLICAPI)
    def _create_by_resume_from(self, resume_from: str, **kwargs):
        """Create a run by specify resume_from to an existing run."""
        stream = kwargs.pop("stream", False)
        run_name = self._service_caller.resume_bulk_run(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            body=self._build_resume_request_rest_object(resume_from=resume_from, **kwargs),
        )

        if stream:
            self.stream(run=run_name)
        return self.get(run=run_name)

    def _resolve_identity(self, run: Run):
        """Resolve identity to resource id"""
        if not run._identity:
            return
        if not isinstance(run._identity, dict):
            raise UserErrorException(
                f"Run's identity should be a dict, got {type(run._resources)} for {run._resources}"
            )
        identity_type = run._identity.get("type")
        # default use user identity
        if identity_type == IdentityKeys.USER_IDENTITY:
            return
        elif identity_type == IdentityKeys.MANAGED:
            client_id = run._identity.get(IdentityKeys.CLIENT_ID)
            if not client_id:
                # use default managed identity
                if not self._workspace.primary_user_assigned_identity:
                    raise UserErrorException(
                        f"Primary user assigned identity not found in workspace {self._workspace.name!r}."
                    )
                resource_id = self._workspace.primary_user_assigned_identity
            else:
                # find client id from the identity
                resource_id = None
                try:
                    for identity in self._workspace.identity.user_assigned_identities or []:
                        if identity.client_id == client_id:
                            resource_id = identity.resource_id
                except Exception:
                    pass
                if not resource_id:
                    raise UserErrorException(
                        f"Failed to get identities with id {client_id} from workspace {self._workspace.name!r}."
                        f"Existing identities: {self._workspace.identity.user_assigned_identities}."
                    )
            run._identity[IdentityKeys.RESOURCE_ID] = resource_id
        else:
            raise UserErrorException(f"Identity type {identity_type!r} is not supported.")

    def _get_telemetry_values(self, *args, **kwargs):
        activity_name = kwargs.get("activity_name", None)
        telemetry_values = super()._get_telemetry_values(*args, **kwargs)
        try:
            if activity_name == "pfazure.runs.create_or_update":
                run: Run = kwargs.get("run", None) or args[0]
                telemetry_values["flow_type"] = run._flow_type
        except Exception as e:
            logger.error(f"Failed to get telemetry values: {str(e)}")

        return telemetry_values

# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import os
import sys
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import requests
import json
from azure.ai.ml._scope_dependent_operations import _ScopeDependentOperations, OperationScope, OperationConfig, \
    OperationsContainer
from azure.ai.ml.constants._common import AzureMLResourceType
from azure.ai.ml.operations import WorkspaceOperations, DataOperations
from azure.ai.ml.operations._operation_orchestrator import OperationOrchestrator
from pandas import DataFrame

from promptflow._cli.pf_logger_factory import _LoggerFactory
from promptflow.azure._load_functions import load_flow
from promptflow.azure._utils.gerneral import get_user_alias_from_credential
from promptflow.sdk._utils import in_jupyter_notebook, incremental_print
from promptflow.sdk._constants import PORTAL_URL_KEY
from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
from promptflow.azure._restclient.flow.models import FlowRunInfo
from promptflow.azure.constants._flow import CHILD_RUNS_PAGE_SIZE
from promptflow.azure.operations import FlowOperations
from promptflow.sdk._constants import AzureRunTypes, ListViewType, RestRunTypes, RunStatus, VisualizeDetailConstants
from promptflow.sdk._utils import render_jinja_template
from promptflow.sdk._visualize_functions import dump_html, generate_html_string
from promptflow.sdk.entities import Run
from promptflow.sdk.exceptions import InvalidRunStatusError

RUNNING_STATUSES = RunStatus.get_running_statuses()

logger = _LoggerFactory.get_logger()


class RunRequestException(Exception):
    """RunRequestException."""

    def __init__(self, message):
        super().__init__(message)


class RunOperations(_ScopeDependentOperations):
    """FlowRunOperations.

    You should not instantiate this class directly. Instead, you should
    create an PFClient instance that instantiates it for you and
    attaches it as an attribute.
    """

    def __init__(
            self,
            operation_scope: OperationScope,
            operation_config: OperationConfig,
            all_operations: OperationsContainer,
            flow_operations: FlowOperations,
            credential,
            **kwargs: Dict,
    ):
        super().__init__(operation_scope, operation_config)
        self._all_operations = all_operations
        workspace = self._workspace_operations.get(name=operation_scope.workspace_name)
        self._service_caller = FlowServiceCaller(workspace, credential)
        self._credential = credential
        self._flow_operations = flow_operations
        self._orchestrators = OperationOrchestrator(self._all_operations, self._operation_scope, self._operation_config)
        self._endpoint_url = self._get_run_history_endpoint_url()

    @property
    def _workspace_operations(self) -> WorkspaceOperations:
        return self._all_operations.get_operation(
            AzureMLResourceType.WORKSPACE, lambda x: isinstance(x, WorkspaceOperations)
        )

    @property
    def _data_operations(self):
        return self._all_operations.get_operation(
            AzureMLResourceType.DATA, lambda x: isinstance(x, DataOperations)
        )

    @property
    def _datastore_operations(self) -> "DatastoreOperations":
        return self._all_operations.all_operations[AzureMLResourceType.DATASTORE]

    def _get_common_azure_url_pattern(self):
        operation_scope = self._operation_scope
        url = (
            f"/subscriptions/{operation_scope.subscription_id}"
            f"/resourceGroups/{operation_scope.resource_group_name}"
            f"/providers/Microsoft.MachineLearningServices"
            f"/workspaces/{operation_scope.workspace_name}"
        )
        return url

    def _get_run_history_endpoint_url(self):
        """Get the endpoint url for the workspace."""
        endpoint = self._service_caller._service_endpoint
        return endpoint + "history/v1.0" + self._get_common_azure_url_pattern()

    def _get_run_portal_url(self, run_id: str):
        """Get the portal url for the run."""
        url = (
            f"https://int.ml.azure.com/prompts/flow/bulkrun/run/{run_id}/details?wsid="
            f"{self._get_common_azure_url_pattern()}&flight=promptfilestorage,PFSourceRun=false"
        )
        return url

    def _get_headers(self):
        token = self._credential.get_token("https://management.azure.com/.default").token
        custom_header = {
            "Authorization": f"Bearer {token}",
            'Content-Type': 'application/json',
        }
        return custom_header

    def create_or_update(self, run: Run, **kwargs):
        stream = kwargs.pop("stream", False)

        flow_path = run.flow
        self._resolve_data_to_asset_id(run=run)
        self._resolve_flow(run=run)
        runtime = run._runtime
        runtime = runtime or kwargs.get("runtime", None)

        rest_obj = run._to_rest_object()
        if runtime:
            if not isinstance(runtime, str):
                raise TypeError(f"runtime should be a string, got {type(runtime)} for {runtime}")
            rest_obj.runtime_name = runtime
            if runtime == "None":
                # HARD CODE for office scenario, use workspace default runtime when specified None
                rest_obj.runtime_name = None
        else:
            logger.warning(
                f"Using automatic runtime, if it's first time you submit flow {flow_path}, "
                "it may take a while to build run time and request may fail with timeout "
                "error and run will stuck with status 'Not started' due to current system limitation. "
                "Wait a while and resubmit same flow can successfully start the run."
            )
            rest_obj.runtime_name = "automatic"
            rest_obj.session_id = self._get_session_id(flow=flow_path)
            rest_obj.vm_size = run._resources.get("instance_type", None)
            rest_obj.max_idle_time_seconds = run._resources.get("idle_time_before_shutdown_minutes", None)
        # This is a temporary workaround until the inputs_mapping format is finalized
        # TODO: remove when inputs_mapping finalized
        if rest_obj.inputs_mapping:
            rest_obj.inputs_mapping = {
                k: v.replace("batch_run.outputs", "variant.outputs") for k, v in rest_obj.inputs_mapping.items()
            }

        self._service_caller.submit_bulk_run(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            body=rest_obj,
            # flow run submission don't support retry for now.
            retry_total=0
        )
        if in_jupyter_notebook():
            print(f"Portal url: {self._get_run_portal_url(run_id=run.name)}")
        if stream:
            self.stream(run=run.name)
        return self.get(run=run.name)

    def list(self, max_results, list_view_type: ListViewType = ListViewType.ACTIVE_ONLY, **kwargs):
        """List runs in the workspace with index service call."""
        headers = self._get_headers()
        filter_archived = []
        if list_view_type == ListViewType.ACTIVE_ONLY:
            filter_archived = ["false"]
        elif list_view_type == ListViewType.ARCHIVED_ONLY:
            filter_archived = ["true"]
        elif list_view_type == ListViewType.ALL:
            filter_archived = ["true", "false"]

        pay_load = {
            "filters": [
                {
                    "field": "type",
                    "operator": "eq",
                    "values": ["runs"]
                },
                {
                    "field": "annotations/archived",
                    "operator": "eq",
                    "values": filter_archived
                },
                {
                    "field": "properties/runType",
                    "operator": "contains",
                    "values": [
                        AzureRunTypes.BATCH,
                        AzureRunTypes.EVALUATION,
                        AzureRunTypes.PAIRWISE_EVALUATE,
                    ]
                }
            ],
            "freeTextSearch": "",
            "order": [
                {
                    "direction": "Desc",
                    "field": "properties/creationContext/createdTime"
                }
            ],
            # index service can return 100 results at most
            "pageSize": min(max_results, 100),
            "skip": 0,
            "includeTotalResultCount": True,
            "searchBuilder": "AppendPrefix"
        }

        endpoint = self._endpoint_url.replace("/history", "/index")
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
            run_id = run["properties"]["runId"]
            run[PORTAL_URL_KEY] = self._get_run_portal_url(run_id=run_id)
            refined_runs.append(Run._from_index_service_entity(run))
        return refined_runs

    def get_metrics(self, run: str, **kwargs) -> dict:
        """Get the metrics from the run.

        :param run: The run
        :type run: str
        :return: The metrics
        :rtype: dict
        """
        run = self._get_run_from_index_service(run)
        metrics = self._get_metrics_from_index_service_run(run)
        return metrics

    def get_details(self, run: str, **kwargs) -> DataFrame:
        """Get the details from the run.

        :param run: The run
        :type run: str
        :return: The details
        :rtype: pandas.DataFrame
        """
        child_runs = self._get_child_runs_from_pfs(run)
        inputs, outputs = self._get_inputs_outputs_from_child_runs(child_runs)
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
        df = pd.DataFrame(data).reindex(columns=columns)
        return df

    def _get_metrics_from_index_service_run(self, run) -> dict:
        """Get the metrics from the index service run."""
        refined_metrics = {}
        metrics = run._metrics
        for metric, value in metrics.items():
            if not "variant" in metric:
                # currently there are some system metrics that are not variant metrics, we will skip them
                continue
            refined_metrics[metric] = value["lastValue"]
        return refined_metrics

    def get(self, run: str, **kwargs) -> Run:
        """Get a run.

        :param run: The run name
        :type run: str
        :return: The run
        :rtype: Run
        """
        return self._get_run_from_run_history(flow_run_id=run, **kwargs)

    def _get_run_from_run_history(self, flow_run_id, **kwargs):
        """Get run info from run history"""
        headers = self._get_headers()
        url = self._endpoint_url + f"/runs/{flow_run_id}"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            run = response.json()
            # add cloud run url
            run[PORTAL_URL_KEY] = self._get_run_portal_url(run_id=flow_run_id)
            run = Run._from_run_history_entity(run)
            return run
        else:
            raise RunRequestException(
                f"Failed to get run from service. Code: {response.status_code}, text: {response.text}"
            )

    def _get_run_from_index_service(self, flow_run_id, **kwargs):
        """Get run info from index service"""
        headers = self._get_headers()
        payload = {
            "filters": [{
                "field": "type",
                "operator": "eq",
                "values": ["runs"]
            }, {
                "field": "annotations/archived",
                "operator": "eq",
                "values": ["false"]
            },
                {
                    "field": "properties/runId",
                    "operator": "eq",
                    "values": [flow_run_id]
                }
            ],
            "order": [{
                "direction": "Desc",
                "field": "properties/startTime"
            }
            ],
            "pageSize": 50,
        }
        endpoint = self._endpoint_url.replace("/history", "/index")
        url = endpoint + f"/entities"
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            runs = response.json().get("value", None)
            if not runs:
                raise RunRequestException(
                    f"Could not found run with run id {flow_run_id!r}, please double check the run id and try again."
                )
            run = runs[0]
            run_id = run["properties"]["runId"]
            run[PORTAL_URL_KEY] = self._get_run_portal_url(run_id=run_id)
            return Run._from_index_service_entity(run)
        else:
            raise RunRequestException(
                f"Failed to get run metrics from service. Code: {response.status_code}, text: {response.text}"
            )

    def archive(self, run_name):
        pass

    def restore(self, run_name):
        pass

    def _get_log(self, flow_run_id: str) -> str:
        return self._service_caller.caller.bulk_runs.get_flow_run_log_content(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            flow_run_id=flow_run_id,
            headers=self._get_headers(),
        )

    def stream(self, run: str):
        """Stream the logs of a run."""
        # TODO: maybe we need to make this configurable
        file_handler = sys.stdout
        # different from Azure ML job, flow job can run very fast, so it might not print anything;
        # use below variable to track this behavior, and at least print something to the user.
        have_printed = False
        try:
            printed = 0
            run = self.get(run=run)
            while run.status in RUNNING_STATUSES or run.status == RunStatus.FINALIZING:
                file_handler.flush()
                available_logs = self._get_log(flow_run_id=run.name)
                printed = incremental_print(available_logs, printed, file_handler)
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
            if run._error:
                error_msg = json.dumps(run._error, indent=4)
                file_handler.write(f'\nError:')
                file_handler.write(error_msg)

        except KeyboardInterrupt:
            error_message = (
                "The output streaming for the flow run was interrupted.\n"
                "But the run is still executing on the cloud.\n"
            )
            print(error_message)

    def _resolve_data_to_asset_id(self, run: Run):
        from azure.ai.ml._artifacts._artifact_utilities import _upload_and_generate_remote_uri
        from azure.ai.ml._utils._arm_id_utils import is_ARM_id_for_resource
        from azure.ai.ml._utils.utils import is_url
        from azure.ai.ml.constants._common import AssetTypes
        from azure.ai.ml.entities._datastore._constants import WORKSPACE_BLOB_STORE

        test_data = run.data

        def _get_data_type(_data):
            if os.path.isdir(_data):
                return AssetTypes.URI_FOLDER
            else:
                return AssetTypes.URI_FILE

        if (
                is_ARM_id_for_resource(test_data)
                or is_url(test_data)
        ):  # Literal value, ARM id or remote url. Pass through
            return

        if os.path.exists(test_data):  # absolute local path, upload, transform to remote url
            data_type = _get_data_type(test_data)
            test_data = _upload_and_generate_remote_uri(
                self._operation_scope,
                self._datastore_operations,
                test_data,
                datastore_name=WORKSPACE_BLOB_STORE,
                show_progress=self._show_progress,
            )
            if data_type == AssetTypes.URI_FOLDER and test_data and not test_data.endswith("/"):
                test_data = test_data + "/"
        else:
            raise ValueError(
                f"Local path {test_data!r} not exist. If it's remote data, only ARM id or remote url is supported."
            )
        run.data = test_data

    def _resolve_flow(self, run: Run):
        flow = load_flow(run.flow)
        self._flow_operations._resolve_arm_id_or_upload_dependencies(flow=flow)
        run.flow = flow.path

    def _get_session_id(self, flow):
        flow = load_flow(flow)
        try:
            user_alias = get_user_alias_from_credential(self._credential)
        except Exception:
            # fall back to unknown user when failed to get credential.
            user_alias = "unknown_user"
        return f"{user_alias}_{Path(flow.code).name}"

    def _get_child_runs_from_pfs(self, run_id: str):
        """Get the child runs from the PFS."""
        headers = self._get_headers()
        endpoint_url = self._endpoint_url.replace("/history/v1.0", "/flow/api")
        url = endpoint_url + f"/BulkRuns/{run_id}/childRuns"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            runs = response.json()
            return runs
        else:
            raise RunRequestException(
                f"Failed to get child runs from service. Code: {response.status_code}, text: {response.text}"
            )

    def _get_inputs_outputs_from_child_runs(self, runs: List[Dict[str, Any]]):
        """Get the inputs and outputs from the child runs."""
        inputs = {}
        outputs = {}
        for run in runs:
            run_inputs, run_outputs = run["inputs"], run["output"]
            if isinstance(run_inputs, dict):
                for k, v in run_inputs.items():
                    if k not in inputs:
                        inputs[k] = []
                    inputs[k].append(v)
            if isinstance(run_outputs, dict):
                for k, v in run_outputs.items():
                    if k not in outputs:
                        outputs[k] = []
                    outputs[k].append(v)
        return inputs, outputs

    @staticmethod
    def _parse_io_spec(run_info: FlowRunInfo) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
        inputs_spec = {k: {"type": v.type} for k, v in run_info.flow_graph.inputs.items()}
        outputs_spec = {k: {"type": v.type} for k, v in run_info.flow_graph.outputs.items()}
        return inputs_spec, outputs_spec

    def _get_data_pagination(self, name: str) -> List[dict]:
        # call childRuns API with pagination to avoid Flow MT OOM
        # different from UX, run status should be completed here
        run_datas = []
        start_index, end_index = 0, CHILD_RUNS_PAGE_SIZE - 1
        while True:
            current_run_datas = self._service_caller.get_child_runs(
                subscription_id=self._operation_scope.subscription_id,
                resource_group_name=self._operation_scope.resource_group_name,
                workspace_name=self._operation_scope.workspace_name,
                flow_run_id=name,
                start_index=start_index,
                end_index=end_index,
            )
            # no data in current page
            if len(current_run_datas) == 0:
                break
            start_index, end_index = start_index + CHILD_RUNS_PAGE_SIZE, end_index + CHILD_RUNS_PAGE_SIZE
            run_datas += current_run_datas
        return run_datas

    @staticmethod
    def _parse_run_data(run_datas: List[dict]) -> List[Dict[str, Any]]:
        data = []
        for run_data in run_datas:
            current_data = {
                "run_id": run_data["run_id"],
                "status": run_data["status"],
                "inputs": copy.deepcopy(run_data["inputs"]),
                "outputs": copy.deepcopy(run_data["output"]),
                "index": run_data["index"],
                "variant_id": run_data["variant_id"],
                "result": copy.deepcopy(run_data["result"]),
            }
            data.append(current_data)
        return data

    def _visualize(self, names: List[str], html_path: Optional[str] = None) -> None:
        run_infos, run_datas = {}, {}
        batch_run_names, eval_run_names = [], []
        print("Preparing data...")
        for name in names:
            # check run status first
            run = self.get(run=name)
            if run.status != RunStatus.COMPLETED:
                error_message = f"Run {name!r} is not completed, please wait for its completion, or select other completed run(s)."
                raise InvalidRunStatusError(error_message)

            # definition
            run_info = self._service_caller.get_bulk_run(
                subscription_id=self._operation_scope.subscription_id,
                resource_group_name=self._operation_scope.resource_group_name,
                workspace_name=self._operation_scope.workspace_name,
                flow_run_id=name
            )
            run_infos[name] = run_info
            if run_info.flow_run_type == RestRunTypes.BATCH:
                batch_run_names.append(name)
            elif run_info.flow_run_type == RestRunTypes.EVALUATION:
                eval_run_names.append(name)
            # data
            run_datas[name] = self._get_data_pagination(name)

        # when only evaluation runs, we need to handle them as batch runs
        if len(batch_run_names) == 0:
            batch_run_names = copy.deepcopy(eval_run_names)
            eval_run_names = []
        data = {}
        # input/output spec
        batch_run_name = batch_run_names[0]
        data["input_spec"], data["output_spec"] = self._parse_io_spec(run_infos[batch_run_name])
        # batch run data
        data["runs_data"] = []
        for batch_run_name in batch_run_names:
            data["runs_data"] += self._parse_run_data(run_datas[batch_run_name])
        # eval run spec & data
        data["eval_runs"] = []
        for eval_run_name in eval_run_names:
            eval_run_info = run_infos[eval_run_name]
            eval_data = {"name": eval_run_name, "display_name": eval_run_info.flow_run_display_name}
            eval_data["input_spec"], eval_data["output_spec"] = self._parse_io_spec(eval_run_info)
            eval_data["runs_data"] = self._parse_run_data(run_datas=run_datas[eval_run_name])
            data["eval_runs"].append(copy.deepcopy(eval_data))
        yaml_string = render_jinja_template(VisualizeDetailConstants.JINJA2_TEMPLATE, **data)
        html_string = generate_html_string(yaml_string)
        # if html_path is specified, not open it in webbrowser(as it comes from VSC)
        dump_html(html_string, html_path, open_html=html_path is None)

    def visualize(self, names: Union[str, Run, List[str], List[Run]], **kwargs) -> None:
        """Visualize run(s).

        :param names: Names of the runs, or list of run objects.
        :type names: Union[str, ~promptflow.sdk.entities.Run, List[str], List[~promptflow.sdk.entities.Run]]
        """
        if not isinstance(names, list):
            names = [names]
        if isinstance(names[0], Run):
            names = [run.name for run in names]
        html_path = kwargs.pop("html_path", None)
        try:
            self._visualize(names, html_path=html_path)
        except Exception as e:  # pylint: disable=broad-except
            raise e



# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os
import sys
import time
import uuid
from typing import Dict, List

import mlflow
from azure.ai.ml._scope_dependent_operations import (
    OperationConfig,
    OperationsContainer,
    OperationScope,
    _ScopeDependentOperations,
)
from azure.ai.ml.constants._common import AzureMLResourceType
from azure.ai.ml.operations import WorkspaceOperations, DataOperations
# we still need v1 SDK for operations like getting child runs; may remove after v2 supports flow.
from azureml._restclient.constants import RunStatus
from azureml.core import Workspace

from promptflow.azure import BulkFlowRun
from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
from promptflow.azure._utils._url_utils import BulkRunURL, BulkRunId
from promptflow.azure.constants import FlowJobType, FlowType

RUNNING_STATUSES = RunStatus.get_running_statuses()


class FlowJobOperations(_ScopeDependentOperations):
    """FlowJobOperations.

    You should not instantiate this class directly. Instead, you should
    create an MLClient instance that instantiates it for you and
    attaches it as an attribute.
    """

    def __init__(
        self,
        operation_scope: OperationScope,
        operation_config: OperationConfig,
        all_operations: OperationsContainer,
        credential,
        **kwargs: Dict,
    ):
        super(FlowJobOperations, self).__init__(operation_scope, operation_config)
        self._all_operations = all_operations
        workspace = self._workspace_operations.get(name=operation_scope.workspace_name)
        self._service_caller = FlowServiceCaller(workspace, credential)
        self._credential = credential
        # workspace in v1 SDK
        self._workspace = Workspace.get(
            name=self._operation_scope.workspace_name,
            subscription_id=self._operation_scope.subscription_id,
            resource_group=self._operation_scope.resource_group_name,
        )
        # set tracking uri for metrics
        mlflow.set_tracking_uri(workspace.mlflow_tracking_uri)

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

    def _get_headers(self):
        token = self._credential.get_token("https://management.azure.com/.default")
        custom_header = {"Authorization": "Bearer " + token.token}
        return custom_header

    def get_bulk_flow_run(self, bulk_test_id: str, flow_id: str) -> BulkFlowRun:
        result = self._service_caller.caller.flows.get_bulk_test(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            flow_id=flow_id,
            bulk_test_id=bulk_test_id,
            headers=self._get_headers(),
        )
        runtime = result.runtime
        return BulkFlowRun(
            flow_id=flow_id,
            bulk_test_id=bulk_test_id,
            runtime=runtime,
        )

    def create_or_update(
            self,
            rest_flow_result,
            test_data,
            connections,
            runtime,
            tuning_node_names=None,
            use_flow_snapshot_to_submit=True,
            **kwargs
    ):
        # TODO: move the parameters inside FlowJob
        from promptflow.azure._restclient.flow.models import (
            SubmitFlowRequest,
            FlowSubmitRunSettings,
            BatchDataInput,
            FlowRunResult
        )

        # resolve data
        test_data = self._resolve_data_to_asset_id(test_data)
        rest_submit_request = SubmitFlowRequest(
            flow_id=rest_flow_result.flow_id,
            flow_run_id=str(uuid.uuid4()),
            flow_submit_run_settings=FlowSubmitRunSettings(
                run_mode="BulkTest",
                batch_data_input=BatchDataInput(
                    data_uri=test_data,
                ),
                runtime_name=runtime,
                tuning_node_names=tuning_node_names,
            ),
            use_workspace_connection=True,
            async_submission=True,
            use_flow_snapshot_to_submit=use_flow_snapshot_to_submit
        )

        # create bulk test
        result: FlowRunResult = self._service_caller.submit_flow(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            experiment_id=rest_flow_result.experiment_id,
            body=rest_submit_request,
        )
        run_id = result.flow_run_resource_id.split("/")[-1]
        studio_url, arm_id = self._get_url(
            experiment_id=rest_flow_result.experiment_id,
            flow_id=rest_flow_result.flow_id,
            bulk_test_id=result.bulk_test_id,
            run_id=run_id,
        )

        return BulkFlowRun._from_flow_run_result(
            flow_id=rest_flow_result.flow_id,
            runtime=runtime,
            experiment_id=rest_flow_result.experiment_id,
            result=result,
            workspace_name=self._operation_scope.workspace_name,
            resource_group_name=self._operation_scope.resource_group_name,
            subscription_id=self._operation_scope.subscription_id,
            flow_type=FlowType.STANDARD,
            studio_url=studio_url,
            arm_id=arm_id,
            run_id=run_id,
        )

    def eval(
            self,
            eval_flow_id,
            test_data,
            runtime,
            flow_id,
            bulk_test_id,
            inputs_mapping,
            bulk_test_flow_run_ids,
            experiment_id,
            connections,
            use_flow_snapshot_to_submit=True,
            **kwargs
    ):
        # TODO: merge with create_or_update
        from promptflow.azure._restclient.flow.models import (
            Flow,
            FlowGraphReference,
            SubmitFlowRequest,
            FlowSubmitRunSettings,
            BatchDataInput,
            EvaluationFlowRunSettings
        )

        # resolve data
        test_data = self._resolve_data_to_asset_id(test_data)
        rest_submit_request = SubmitFlowRequest(
            flow_id=flow_id,
            flow_run_id=str(uuid.uuid4()),
            flow=Flow(
                evaluation_flows={
                    "evaluation": FlowGraphReference(
                        reference_resource_id=eval_flow_id
                    )
                }
            ),
            flow_submit_run_settings=FlowSubmitRunSettings(
                run_mode="Eval",
                bulk_test_id=bulk_test_id,
                batch_data_input=BatchDataInput(
                    data_uri=test_data,
                ),
                runtime_name=runtime,
                inputs_mapping=inputs_mapping,
                bulk_test_flow_run_ids=bulk_test_flow_run_ids,
                evaluation_flow_run_settings={
                    "evaluation": EvaluationFlowRunSettings(
                        inputs_mapping=inputs_mapping,
                        connection_overrides=connections
                    )
                }
            ),
            use_workspace_connection=True,
            async_submission=True,
            use_flow_snapshot_to_submit=use_flow_snapshot_to_submit
        )

        # create evaluation
        result = self._service_caller.submit_flow(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            experiment_id=experiment_id,
            body=rest_submit_request,
        )

        # TODO: refactor this
        evaluation_run_id = result.flow_run_resource_id.split("/")[-1]

        studio_url, arm_id = self._get_url(
            experiment_id=experiment_id,
            flow_id=flow_id,
            bulk_test_id=result.bulk_test_id,
            run_id=evaluation_run_id
        )

        run = BulkFlowRun._from_flow_run_result(
            flow_id=flow_id,
            runtime=runtime,
            experiment_id=experiment_id,
            result=result,
            workspace_name=self._operation_scope.workspace_name,
            resource_group_name=self._operation_scope.resource_group_name,
            subscription_id=self._operation_scope.subscription_id,
            flow_type=FlowType.EVALUATION,
            studio_url=studio_url,
            arm_id=arm_id,
            run_id=evaluation_run_id,
        )
        return run

    def _resolve_data_to_asset_id(self, test_data):
        from azure.ai.ml.entities import Data
        from azure.ai.ml._utils._arm_id_utils import parse_prefixed_name_version

        if os.path.exists(test_data):
            # create anonymous data to remote
            if os.path.isdir(test_data):
                data_type = "uri_folder"
            else:
                data_type = "uri_file"
            data = Data(path=test_data, name=str(uuid.uuid4()), version="1.0.0", type=data_type)
            data._is_anonymous = True
            data = self._data_operations.create_or_update(
                data=data,
            )
        else:
            name, version = parse_prefixed_name_version(test_data)
            data = self._data_operations.get(name=name, version=version)
        return data.id

    def _get_url(self, experiment_id, flow_id, bulk_test_id, run_id):
        studio_url = BulkRunURL.get_url(
            experiment_id, flow_id, bulk_test_id,
            subscription_id=self._operation_scope.subscription_id,
            resource_group=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
        )
        #print(f"Studio URL: {studio_url}")

        arm_id = BulkRunId.get_url(experiment_id, flow_id, bulk_test_id, run_id=run_id)
        return studio_url, arm_id

    def _get_log(self, flow_id: str, flow_run_id: str) -> str:
        return self._service_caller.caller.flows.get_flow_run_log_content(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            flow_id=flow_id,
            flow_run_id=flow_run_id,
            headers=self._get_headers(),
        )

    def get_child_run_ids(self, run_id: str, flow_type: str) -> List[Dict[str, str]]:
        child_run_type = FlowJobType.STANDARD if flow_type == FlowType.STANDARD else FlowJobType.EVALUATION
        return [child_run.id for child_run in self._workspace.get_run(run_id=run_id).get_children(type=child_run_type)]

    def get_child_run_infos(self, run_id: str, flow_id: str, flow_type: str) -> List[Dict[str, str]]:
        # NOTE: Flow MT does not have API for getting standard/evaluation run under a bulk flow run,
        #       so we need to call index service/RH to get child runs; currently we leverage v1 SDK,
        #       should switch to v2 SDK after MFE support flow type job.
        child_run_ids = self.get_child_run_ids(run_id, flow_type)
        child_run_infos = []
        for child_run_id in child_run_ids:
            result = self._service_caller.caller.flows.get_flow_child_runs(
                subscription_id=self._operation_scope.subscription_id,
                resource_group_name=self._operation_scope.resource_group_name,
                workspace_name=self._operation_scope.workspace_name,
                flow_id=flow_id,
                flow_run_id=child_run_id,
                headers=self._get_headers(),
            )
            # MT currently has bug on the response for base flow run,
            # workaround by a flag variable
            next_child_run = False
            for child_run_info in result:
                if child_run_info["request"] is not None:
                    next_child_run = True
                    break
                if flow_type == "standard":
                    child_run_infos.append(
                        {
                            "index": child_run_info["index"],
                            "inputs": child_run_info["inputs"],
                            "variant_id": child_run_info["variant_id"],
                            "output": child_run_info["output"],                    
                        }
                    )
                else:
                    child_run_infos.append(
                        {
                            "index": child_run_info["index"],
                            "inputs": child_run_info["inputs"],
                            "output": child_run_info["output"],                    
                        }
                    )
            if next_child_run is True:
                continue
        return child_run_infos

    def get_metrics(self, bulk_test_id: str) -> Dict[str, dict]:
        child_run_ids = [child_run.id for child_run in self._workspace.get_run(run_id=bulk_test_id).get_children(type=FlowJobType.EVALUATION)]
        evaluation_flow_metrics = {}
        for child_run_id in child_run_ids:
            evaluation_flow = mlflow.get_run(run_id=child_run_id)
            evaluation_flow_metrics[child_run_id] = evaluation_flow.data.metrics.copy()
        return evaluation_flow_metrics

    def _stream_flow_run(self, flow_id: str, flow_run_id: str, file_handler) -> None:
        # reference from v1 SDK `_stream_run_output`:
        # https://msdata.visualstudio.com/Vienna/_git/AzureMlCli?path=/src/azureml-core/azureml/core/run.py&version=GBmaster&line=994&lineEnd=995&lineStartColumn=1&lineEndColumn=1&lineStyle=plain&_a=contents

        def _incremental_print(_log: str, _printed: int, _fileout):
            _count = 0
            for _line in _log.splitlines():
                if _count >= _printed:
                    _fileout.write(_line + "\n")
                    _printed += 1
                _count += 1
            return _printed

        printed = 0
        run = self._workspace.get_run(run_id=flow_run_id)
        while run.status in RUNNING_STATUSES or run.status == RunStatus.FINALIZING:
            file_handler.flush()
            available_logs = self._get_log(flow_id=flow_id, flow_run_id=flow_run_id)
            printed = _incremental_print(available_logs, printed, file_handler)
            time.sleep(10)
            run = self._workspace.get_run(run_id=flow_run_id)
        # ensure all logs are printed
        file_handler.flush()
        available_logs = self._get_log(flow_id=flow_id, flow_run_id=flow_run_id)
        _incremental_print(available_logs, printed, file_handler)

        file_handler.write("=================\n")
        file_handler.write(f"RunId: {flow_run_id}\n")
        file_handler.write(f"Web View: {run.get_portal_url()}\n\n")

    def stream(self, bulk_test_id: str, flow_id: str, flow_type: str) -> None:
        processed_child_runs = []
        run = self._workspace.get_run(run_id=bulk_test_id)

        child_run_type = FlowJobType.STANDARD if flow_type == FlowType.STANDARD else FlowJobType.EVALUATION

        # TODO: maybe we need to make this configurable
        file_handler = sys.stdout
        # different from Azure ML job, flow job can run very fast, so it might not print anything;
        # use below variable to track this behavior, and at least print something to the user.
        have_printed = False
        try:
            while run.status in RUNNING_STATUSES:
                have_printed = True
                for child_run in run.get_children(type=child_run_type):
                    if child_run.id not in processed_child_runs:
                        processed_child_runs.append(child_run.id)
                        self._stream_flow_run(flow_id=flow_id, flow_run_id=child_run.id, file_handler=file_handler)
                run = self._workspace.get_run(run_id=bulk_test_id)
            
            if not have_printed:
                file_handler.write(f"Bulk flow run {bulk_test_id} is already finished, below will print logs for all child flow runs:\n")
                for child_run in run.get_children():
                    self._stream_flow_run(flow_id=flow_id, flow_run_id=child_run.id, file_handler=file_handler)

            # NOTE: for fast flow run (e.g. evaluation flow run), there might need some seconds
            #       to make data available from API, so we sleep a little bit here.
            time.sleep(3)

            file_handler.write("=================\n")
            file_handler.write(f"BulkFlowRunId: {bulk_test_id}\n")
            file_handler.write(f"Web View: {run.get_portal_url()}\n")

        except KeyboardInterrupt:
            error_message = (
                "The output streaming for the bulk flow run interrupted.\n"
                "But the bulk flow run is still executing on the cloud.\n"
            )
            print(error_message)

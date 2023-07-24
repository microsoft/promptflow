import json
import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from azure.core.exceptions import ResourceModifiedError

from promptflow._constants import PromptflowEdition
from promptflow.contracts.azure_storage_setting import AzureStorageSetting
from promptflow.contracts.run_info import FlowRunInfo, RunInfo
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_info import Status as PromptflowRunStatus
from promptflow.exceptions import (
    AzureStorageOperationError,
    ErrorResponse,
    ErrorTarget,
    StorageAuthenticationError,
    SystemErrorException,
    UserErrorException,
)
from promptflow.runtime.utils import logger
from promptflow.runtime.utils._asset_client import AssetClient
from promptflow.runtime.utils._run_history_client import RunHistoryClient
from promptflow.storage.common import reconstruct_metrics_dict
from promptflow.storage.run_storage import AbstractRunStorage
from promptflow.utils.dataclass_serializer import serialize
from promptflow.utils.logger_utils import bulk_logger, flow_logger
from promptflow.utils.retry_utils import retry
from promptflow.utils.timer import Timer
from promptflow.utils.utils import is_in_ci_pipeline

try:
    import mlflow
    from azure.core.credentials import AzureNamedKeyCredential
    from azure.core.exceptions import (
        ClientAuthenticationError,
        HttpResponseError,
        ResourceExistsError,
        ResourceNotFoundError,
    )
    from azure.storage.blob import BlobServiceClient
    from mlflow.entities.run import Run as MlflowRun
    from mlflow.entities.run_status import RunStatus as MlflowRunStatus
    from mlflow.exceptions import RestException
    from mlflow.protos.databricks_pb2 import BAD_REQUEST, RESOURCE_DOES_NOT_EXIST, ErrorCode
    from mlflow.tracking import MlflowClient
    from mlflow.utils.rest_utils import http_request
except ImportError as e:
    msg = f"Please install azure-related packages, currently got {str(e)}"
    raise UserErrorException(message=msg, target=ErrorTarget.AZURE_RUN_STORAGE)


class StorageOperations(Enum):
    UPDATE = "update"
    CREATE = "create"


class RuntimeAuthErrorType:
    WORKSPACE = "workspace"
    STORAGE = "storage"


RunStatusMapping = {
    PromptflowRunStatus.Completed.value: MlflowRunStatus.to_string(MlflowRunStatus.FINISHED),
    PromptflowRunStatus.Failed.value: MlflowRunStatus.to_string(MlflowRunStatus.FAILED),
    PromptflowRunStatus.Canceled.value: MlflowRunStatus.to_string(MlflowRunStatus.KILLED),
}


def _blob_error_handling_decorator(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except ResourceExistsError as e:
            original_msg = str(e)
            refined_error_msg = (
                f"Failed to upload write to blob because trying to "
                "create a new blob with an existing name. "
                f"Original error: {original_msg}"
            )
            logger.error(refined_error_msg)
            raise AzureStorageOperationError(
                message=refined_error_msg,
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e
        except Exception as e:
            original_msg = str(e)
            refined_error_msg = f"Failed to upload run info to blob. Original error: {original_msg}"
            logger.error(refined_error_msg)
            raise AzureStorageOperationError(
                message=refined_error_msg,
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e

    return wrapper


class AzureMLRunStorageV2(AbstractRunStorage):
    FLOW_ARTIFACTS_FOLDER_NAME = "flow_artifacts"
    NODE_ARTIFACTS_FOLDER_NAME = "node_artifacts"
    FLOW_OUTPUTS_FOLDER_NAME = "flow_outputs"
    META_FILE_NAME = "meta.json"
    DEFAULT_BATCH_SIZE = 25
    LINE_NUMBER_WIDTH = 9

    FLOW_RUN_INFO_PROPERTIES_TO_UPDATE = AbstractRunStorage.FLOW_RUN_INFO_PROPERTIES_TO_UPDATE

    def __init__(
        self,
        azure_storage_setting: AzureStorageSetting,
        mlflow_tracking_uri: str,
        ml_client,
        run_history_client: RunHistoryClient,
        asset_client: AssetClient,
    ) -> None:
        super().__init__(edition=PromptflowEdition.ENTERPRISE)
        if not ml_client:
            raise SystemErrorException(
                message="Failed to initialize AzureMLRunStorageV2: 'ml_client' cannot be empty.",
                target=ErrorTarget.AZURE_RUN_STORAGE,
            )

        self.flow_artifacts_root_path = azure_storage_setting.flow_artifacts_root_path.strip("/")
        self.output_datastore_name = azure_storage_setting.output_datastore_name
        self._mlflow_helper = MlflowHelper(mlflow_tracking_uri=mlflow_tracking_uri)
        self._ml_client = ml_client
        self._run_history_client = run_history_client
        self._asset_client = asset_client
        self._persisted_runs = set()
        self._batch_size = self.DEFAULT_BATCH_SIZE

        self.init_azure_blob_service_client(
            storage_account_name=azure_storage_setting.storage_account_name,
            blob_container_name=azure_storage_setting.blob_container_name,
            credential=azure_storage_setting.blob_container_sas_token,
        )
        self._write_flow_artifacts_meta_to_blob()

    def init_azure_blob_service_client(self, storage_account_name, blob_container_name, credential):
        """Initialize blob service client"""
        # AzureNameKeyCredential is supported from blob version 12.14.0, while currently we have blob version 12.13.0
        # due to azureml-mlflow package requirement. So we need extra process to make this work

        blob_url = f"https://{storage_account_name}.blob.core.windows.net"

        if isinstance(credential, AzureNamedKeyCredential):
            named_key = credential.named_key
            credential = {"account_name": named_key[0], "account_key": named_key[1]}

        blob_service_client = BlobServiceClient(blob_url, credential=credential)

        try:
            container = blob_service_client.get_container_client(blob_container_name)
        except HttpResponseError as e:
            msg = str(e)
            if e.status_code == 403:
                auth_error_msg = (
                    "Failed to perform azure blob operation due to invalid authentication, please assign RBAC role "
                    f"'Storage Blob Data Contributor' to the service principal or client. Original error: {msg}"
                )
                logger.error(auth_error_msg)
                raise StorageAuthenticationError(
                    message=auth_error_msg,
                    target=ErrorTarget.AZURE_RUN_STORAGE,
                ) from e

            logger.error(f"Failed to perform azure blob operation due to invalid authentication. Original error: {msg}")
            raise

        self.blob_container_client = container
        logger.info("Initialized blob service client for AzureMLRunTracker.")

    def refine_the_run_record(self, run_records, properties=None):
        """Refine and persist the run record."""
        record_dict = run_records.__dict__
        if properties:
            return {k: record_dict[k] for k in properties}
        return record_dict

    def persist_node_run(self, run_info: RunInfo):
        """Persist node run record to remote storage"""
        with Timer(flow_logger, "Persist node info for run " + run_info.run_id):
            record_dict = self.refine_the_run_record(IntermediateRunRecords.from_run_info(run_info))
            # For reduce nodes, the 'line_number' is None, we store the info in the 000000000.jsonl file
            # It's a storage contract with PromptflowService
            file_name = f"{str(record_dict.get('line_number') or 0).zfill(self.LINE_NUMBER_WIDTH)}.jsonl"
            blob_path = (
                f"{self.flow_artifacts_root_path}/{self.NODE_ARTIFACTS_FOLDER_NAME}/"
                f"{record_dict['NodeName']}/{file_name}"
            )
            blob_client = self.blob_container_client.get_blob_client(blob=blob_path)
            self.upload_blob(blob_client, json.dumps(record_dict), overwrite=True)

            # partial record with blob path is persisted to table
            record_dict["run_info"] = self.get_relative_path_in_blob(blob_client)

    def persist_flow_run(self, run_info: FlowRunInfo):
        """Persist flow run record to remote storage"""
        if not Status.is_terminated(run_info.status):
            logger.info("Flow run is not terminated, skip persisting flow run record.")
            return

        if self._is_root_run(run_info):
            with Timer(flow_logger, "Persist root run info for run " + run_info.run_id):
                self._upload_metrics(run_info)
                self._update_run_history_properties(run_info)
                if run_info.status == Status.Completed:
                    self._write_root_run_info(run_info)
                    asset_id = self._create_flow_output_asset(run_info)
                    self._run_history_client.patch_run(run_info.root_run_id, asset_id)
                # end the root flow run that was created in azure machine learning workspace
                self._end_aml_root_run(run_info=run_info)
        else:
            with Timer(flow_logger, "Persist flow run info for run " + run_info.run_id):
                record_dict = self.refine_the_run_record(FlowRecords.from_run_info(run_info))
                lower_bound = record_dict["line_number"] // self._batch_size * self._batch_size
                upper_bound = lower_bound + self._batch_size - 1
                file_name = (
                    f"{str(lower_bound).zfill(self.LINE_NUMBER_WIDTH)}_"
                    f"{str(upper_bound).zfill(self.LINE_NUMBER_WIDTH)}.jsonl"
                )
                blob_path = f"{self.flow_artifacts_root_path}/{self.FLOW_ARTIFACTS_FOLDER_NAME}/{file_name}"
                blob_client = self.blob_container_client.get_blob_client(blob=blob_path)
                self.append_blob(blob_client, json.dumps(record_dict) + "\n")

    def update_flow_run_info(self, run_info: FlowRunInfo):
        """Update the following flow run info fields: status, end_time, run_info"""
        # Update run history status and metrics
        self.persist_flow_run(run_info)

    def persist_status_summary(self, metrics: dict, flow_run_id: str):
        self._mlflow_helper.persist_status_summary(metrics=metrics, flow_run_id=flow_run_id)

    def _update_run_history_properties(self, run_info: FlowRunInfo):
        self._mlflow_helper.update_run_history_properties(run_info=run_info)

    def _upload_metrics(self, run_info: FlowRunInfo):
        self._mlflow_helper.upload_metrics_to_run_history(run_info=run_info)

    def _create_flow_output_asset(self, run_info: FlowRunInfo):
        output_blob_folder_path = f"{self.flow_artifacts_root_path}/{self.FLOW_OUTPUTS_FOLDER_NAME}/"
        output_blob_file_name = f"{output_blob_folder_path}output.jsonl"
        output_blob_client = self.blob_container_client.get_blob_client(blob=output_blob_file_name)
        output_json_lines = self._serialize_outputs_to_json_lines(run_info.output)
        self.upload_blob(output_blob_client, output_json_lines, overwrite=True)
        asset_id = self._asset_client.create_unregistered_output(
            run_id=run_info.root_run_id,
            datastore_name=self.output_datastore_name,
            relative_path=output_blob_folder_path,
        )
        logger.info(f"Created output Asset: {asset_id}")
        return asset_id

    def _write_root_run_info(self, run_info: FlowRunInfo):
        # Deleberately remove output and result from root run info to avoid reading full output/result from API
        run_info_copy = deepcopy(run_info)
        run_info_copy.output = None
        run_info_copy.result = None
        record_dict = self.refine_the_run_record(FlowRecords.from_run_info(run_info_copy))
        blob_path = f"{self.flow_artifacts_root_path}/run_info.json"
        blob_client = self.blob_container_client.get_blob_client(blob=blob_path)
        self.upload_blob(blob_client, json.dumps(record_dict["run_info"]), overwrite=True)

    def _write_flow_artifacts_meta_to_blob(self):
        blob_path = f"{self.flow_artifacts_root_path}/{self.META_FILE_NAME}"
        blob_client = self.blob_container_client.get_blob_client(blob=blob_path)
        meta = {"batch_size": self._batch_size}
        self.upload_blob(blob_client, json.dumps(meta), overwrite=True)

    @_blob_error_handling_decorator
    def upload_blob(self, blob_client, blob_entity: str, overwrite=True):
        """Try write azure blob and handle the exceptions"""
        # note all auth related error are already handled in the constructor
        blob_client.upload_blob(blob_entity, overwrite=overwrite)

    @_blob_error_handling_decorator
    def append_blob(self, blob_client, append_content: str):
        """Try append azure blob and handle the exceptions"""
        # note all auth related error are already handled in the constructor
        # Do not use blob_client.exists because it's not atomic with creation and introduce race dondition
        try:
            blob_client.create_append_blob(if_unmodified_since=datetime(2000, 1, 1, tzinfo=timezone.utc))
        except ResourceModifiedError:
            pass
        blob_client.append_block(data=append_content)

    def get_flow_run(self, run_id: str, flow_id=None) -> FlowRunInfo:
        return None

    def get_relative_path_in_blob(self, blob_client) -> str:
        """Get a json string that indicates the container and relative path in remote blob"""
        blob_path_info = {
            "container": blob_client.container_name,
            "relative_path": blob_client.blob_name,
        }
        return json.dumps(blob_path_info)

    def _start_aml_root_run(self, run_id: str) -> None:
        """Update root run that gets created by MT to running status"""
        self._mlflow_helper.start_run(run_id=run_id, create_if_not_exist=True)

    def _end_aml_root_run(self, run_info: FlowRunInfo, ex: Exception = None) -> None:
        """Update root run to end status"""
        # if error detected, write error info to run history
        error_response = self._get_error_response_dict(run_info, ex=ex)
        if error_response:
            current_run = mlflow.active_run()
            self._mlflow_helper.write_error_message(mlflow_run=current_run, error_response=error_response)

        # end the aml run here
        self._mlflow_helper.end_run(run_id=run_info.run_id, status=run_info.status.value)

    def _end_aml_bulk_test_run(self, bulk_test_id: str, bulk_test_status: str) -> None:
        """Update bulk test run to end status"""
        self._mlflow_helper.end_run(run_id=bulk_test_id, status=bulk_test_status)

    def cancel_run(self, run_id: str):
        """Cancel an aml root run"""
        self._mlflow_helper.cancel_run(run_id=run_id)

    def get_run_status(self, run_id: str):
        """Get run status of an aml run"""
        run_status = None
        try:
            run_info = self._ml_client.jobs._runs_operations.get_run(run_id=run_id)
        except ResourceNotFoundError as e:
            # skip if the run is not found, will return status "None"
            logger.warning(f"Failed to get run status of run {run_id!r} due to run not found: {str(e)}")
        else:
            run_status = run_info.status
        return run_status

    def _get_error_response_dict(self, run_info: FlowRunInfo, ex: Exception) -> dict:
        """Get the error response dict from run info error or exception"""
        result = None
        run_info_error = run_info.error
        if run_info_error and isinstance(run_info_error, dict) and len(run_info_error) > 0:
            result = ErrorResponse.from_error_dict(run_info_error).to_dict()
        elif ex:
            result = ErrorResponse.from_exception(ex).to_dict()
        return result

    def _is_root_run(self, run_info: FlowRunInfo) -> bool:
        return run_info.run_id == run_info.root_run_id

    def _serialize_outputs_to_json_lines(self, output_dict):
        keys = output_dict.keys()
        values = zip(*output_dict.values())
        pivoted = [{"line_number": i, **dict(zip(keys, v))} for i, v in enumerate(values)]
        output_str = "\n".join([json.dumps(o) for o in pivoted])
        return output_str


class MlflowHelper:
    ERROR_EVENT_NAME = "Microsoft.MachineLearning.Run.Error"
    ERROR_MESSAGE_SET_MULTIPLE_TERMINAL_STATUS = "Cannot set run to multiple terminal states"
    RUN_HISTORY_TOTAL_TOKENS_PROPERTY_NAME = "azureml.promptflow.total_tokens"

    def __init__(self, mlflow_tracking_uri):
        """Set mlflow tracking uri to target uri"""
        self.enable_usage_in_ci_pipeline_if_needed()
        if isinstance(mlflow_tracking_uri, str) and mlflow_tracking_uri.startswith("azureml:"):
            logger.info(f"Setting mlflow tracking uri to {mlflow_tracking_uri!r}")
            mlflow.set_tracking_uri(mlflow_tracking_uri)
        else:
            message = (
                f"Mlflow tracking uri must be a string that starts with 'azureml:', "
                f"got {mlflow_tracking_uri!r} with type {type(mlflow_tracking_uri)!r}."
            )
            raise UserErrorException(message=message, target=ErrorTarget.AZURE_RUN_STORAGE)

        self.client = MlflowClient()
        # modify client cred to be used in run history api call
        api_call_cred = self.get_api_call_cred()
        api_call_cred.host = api_call_cred.host.replace("mlflow/v2.0", "mlflow/v1.0").replace(
            "mlflow/v1.0", "history/v1.0"
        )
        self.api_call_cred = api_call_cred

    # mlflow client get credential may return ClientAuthenticationError transiently even with correct credential
    @retry(ClientAuthenticationError, tries=5, delay=0.5, backoff=1)
    def get_api_call_cred(self):
        return self.client._tracking_client.store.get_host_creds()

    def enable_usage_in_ci_pipeline_if_needed(self):
        if is_in_ci_pipeline():
            # this is to enable mlflow use CI SP client credential
            # Refer to: https://learn.microsoft.com/en-us/azure/machine-learning/how-to-use-mlflow-configure-tracking?view=azureml-api-2&tabs=python%2Cmlflow#configure-authentication  # noqa: E501
            os.environ["AZURE_TENANT_ID"] = os.environ.get("tenantId")
            os.environ["AZURE_CLIENT_ID"] = os.environ.get("servicePrincipalId")
            os.environ["AZURE_CLIENT_SECRET"] = os.environ.get("servicePrincipalKey")

    def start_run(self, run_id: str, create_if_not_exist: bool = False):
        try:
            logger.info(
                f"Starting the aml run {run_id!r}...",
            )
            mlflow.start_run(run_id=run_id)
        except Exception as e:
            msg = str(e)
            if (
                create_if_not_exist
                and isinstance(e, RestException)
                and e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST)
            ):
                logger.warning(f"Run {run_id!r} not found, will create a new run with this run id.")
                self.create_run(run_id=run_id)
                return
            raise SystemErrorException(
                f"Failed to start root run {run_id!r} in workspace through mlflow: {msg}",
                target=ErrorTarget.AZURE_RUN_STORAGE,
                error=e,
            )

    def create_run(self, run_id: str, start_after_created=True, backoff_factor=None):
        """Create a run with specified run id"""
        response = http_request(
            host_creds=self.api_call_cred,
            endpoint="/experiments/{}/runs/{}".format("Default", run_id),
            method="PATCH",
            json={"runId": run_id},
            backoff_factor=backoff_factor,
        )
        if response.status_code == 200:
            if start_after_created:
                try:
                    mlflow.start_run(run_id=run_id)
                except Exception as e:
                    raise SystemErrorException(
                        f"A new run {run_id!r} is created but failed to start it: {str(e)}",
                        target=ErrorTarget.AZURE_RUN_STORAGE,
                    )
        else:
            raise SystemErrorException(
                f"Failed to create run {run_id!r}: {response.text}",
                target=ErrorTarget.AZURE_RUN_STORAGE,
            )

    def end_run(self, run_id: str, status: str):
        """Update root run to end status"""
        if status not in RunStatusMapping:
            raise SystemErrorException(
                message="Trying to end a workspace root run with non-terminated status.",
                target=ErrorTarget.AZURE_RUN_STORAGE,
            )
        mlflow_status = RunStatusMapping[status]

        try:
            logger.info(
                f"Ending the aml run {run_id!r} with status {status!r}...",
            )
            mlflow.end_run(status=mlflow_status)
        except Exception as e:
            if isinstance(e, RestException) and self.ERROR_MESSAGE_SET_MULTIPLE_TERMINAL_STATUS in e.message:
                logger.warning(f"Failed to set run {run_id!r} to {status!r} since it is already ended.")
                return
            raise SystemErrorException(
                f"Failed to end root run {run_id!r} in workspace through mlflow: {str(e)}",
                target=ErrorTarget.AZURE_RUN_STORAGE,
                error=e,
            )

    def active_run(self):
        """Get current active run"""
        return mlflow.active_run()

    def cancel_run(self, run_id: str):
        """Cancel a specific run"""
        logger.info(f"Getting current active run {run_id!r}...")
        current_run = mlflow.active_run()
        if current_run and current_run.info.run_id != run_id:
            message = f"Failed to cancel run {run_id!r} since there is another active run {current_run.info.run_id!r}."
            raise SystemErrorException(
                message=message,
                target=ErrorTarget.AZURE_RUN_STORAGE,
            )
        try:
            logger.info(f"Resuming existing run {run_id!r}...")
            mlflow.start_run(run_id=run_id)
            logger.info(f"Cancelling run {run_id!r}...")
            mlflow.end_run(status=MlflowRunStatus.to_string(MlflowRunStatus.KILLED))
        except Exception as e:
            msg = str(e)
            if (
                isinstance(e, RestException)
                and e.error_code == ErrorCode.Name(BAD_REQUEST)
                and self.ERROR_MESSAGE_SET_MULTIPLE_TERMINAL_STATUS in msg
            ):
                logger.warning(f"Run {run_id!r} is already in terminal states, skipped cancel request.")
                return

            raise SystemErrorException(
                f"Failed to cancel root run {run_id!r} in workspace through mlflow: {msg}",
                target=ErrorTarget.AZURE_RUN_STORAGE,
                error=e,
            )

    def write_error_message(self, mlflow_run: MlflowRun, error_response: dict):
        """Write error message to run history with specified exception info"""
        run_id = mlflow_run.info.run_id
        experiment_id = mlflow_run.info.experiment_id
        error_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "name": self.ERROR_EVENT_NAME,
            "data": {
                "errorResponse": error_response,
            },
        }
        response = http_request(
            host_creds=self.api_call_cred,
            endpoint="/experimentids/{}/runs/{}/events".format(experiment_id, run_id),
            method="POST",
            json=error_event,
        )
        if response.status_code != 200:
            message = (
                f"Failed to write error message to run history for run {run_id!r}, response status code: "
                f"{response.status_code!r}, response message: {response.text!r}"
            )
            logger.warning(message)

    def update_run_history_properties(self, run_info: FlowRunInfo):
        current_run = mlflow.active_run()
        if not current_run:
            # warning when there is no active aml run, not raise exception in case the issue is from mlflow itself.
            logger.warning("No active aml run found, make sure run tracker has started a aml run")
            return

        # current_run.info.run_id == run_info.run_id in this context
        run_id = current_run.info.run_id
        # run_info does not have experiment_id, so we get from current_run from mflow
        experiment_id = current_run.info.experiment_id

        properties = {
            # Write total_tokens into RH (RunDto.Properties), For example, "azureml.promptflow.total_tokens": "12"
            # System_metrics["total_tokens"] is integer. We write 0 if this metrics not exist
            self.RUN_HISTORY_TOTAL_TOKENS_PROPERTY_NAME: run_info.system_metrics.get("total_tokens", 0)
        }

        with Timer(bulk_logger, "Upload RH properties for run " + run_id):
            response = http_request(
                host_creds=self.api_call_cred,
                endpoint="/experimentids/{}/runs/{}".format(experiment_id, run_id),
                method="PATCH",
                json={"runId": run_id, "properties": properties},
            )

            if response.status_code == 200:
                logger.info(f"Successfully write run properties {json.dumps(properties)} with run id '{run_id}'")
            else:
                logger.warning(
                    f"Failed to write run properties {json.dumps(properties)} with run id {run_id}. "
                    f"Code: {response.status_code}, text: {response.text}"
                )

    def upload_metrics_to_run_history(self, run_info: FlowRunInfo):
        """Upload metrics to run history via mlflow"""
        metrics = run_info.metrics
        if isinstance(metrics, dict) and len(metrics) > 0:
            # There should be a root aml run that was created by MT when we try to log metrics for.
            # Run tracker will start this aml run when executing the flow run and here we should get the active run.
            current_run = mlflow.active_run()
            if not current_run:
                # warning when there is no active aml run, not raise exception in case the issue is from mlflow itself.
                logger.warning(
                    "No active aml run found, make sure run tracker has started a aml run to log metrics for."
                )
                return

            # start to log metrics to aml run
            with Timer(bulk_logger, "Upload metrics for run " + run_info.run_id):
                try:
                    new_metrics = reconstruct_metrics_dict(metrics)
                    for metric_name, value in new_metrics.items():
                        # use mlflow api to upload refined metric
                        mlflow.log_metric(metric_name, value)
                except Exception as e:
                    logger.warning(f"Failed to upload metrics to workspace: {str(e)}")
        elif metrics is not None:
            logger.warning(f"Metrics should be a dict but got a {type(metrics)!r} with content {metrics!r}")

    def persist_status_summary(self, metrics: dict, flow_run_id: str):
        """Upload status summary metrics to run history via mlflow"""
        if isinstance(metrics, dict) and len(metrics) > 0:
            # There should be a root aml run that was created by MT when we try to log metrics for.
            # Run tracker will start this aml run when executing the flow run and here we should get the active run.
            current_run = mlflow.active_run()
            if not current_run:
                # warning when there is no active aml run, not raise exception in case the issue is from mlflow itself.
                logger.warning(
                    "No active aml run found, make sure run tracker has started a aml run to log metrics for."
                )
                return

            # start to log metrics to aml run
            with Timer(bulk_logger, "Upload status summary metrics for run " + flow_run_id):
                try:
                    for metric_name, value in metrics.items():
                        # use mlflow api to status summary inner metric
                        mlflow.log_metric(metric_name, value)
                except Exception as e:
                    logger.warning(f"Failed to upload status summary metrics to workspace: {str(e)}")
        elif metrics is not None:
            logger.warning(f"Metrics should be a dict but got a {type(metrics)!r} with content {metrics!r}")


@dataclass
class IntermediateRunRecords:
    NodeName: str
    line_number: int
    run_info: str
    start_time: datetime
    end_time: datetime
    status: str

    @staticmethod
    def from_run_info(run_info: RunInfo) -> "IntermediateRunRecords":
        return IntermediateRunRecords(
            NodeName=run_info.node,
            line_number=run_info.index,
            run_info=serialize(run_info),
            start_time=run_info.start_time.isoformat(),
            end_time=run_info.end_time.isoformat(),
            status=run_info.status.value,
        )


@dataclass
class FlowRecords:
    line_number: int
    run_info: str
    start_time: datetime
    end_time: datetime
    name: str
    description: str
    status: str
    tags: str

    @staticmethod
    def from_run_info(run_info: FlowRunInfo) -> "FlowRecords":
        return FlowRecords(
            line_number=run_info.index,
            run_info=serialize(run_info),
            start_time=run_info.start_time.isoformat(),
            end_time=run_info.end_time.isoformat(),
            name=run_info.name,
            description=run_info.description,
            status=run_info.status.value,
            tags=run_info.tags,
        )

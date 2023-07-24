import json
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List

from promptflow._constants import (
    TABLE_LIMIT_ENTITY_SIZE,
    TABLE_LIMIT_PROPERTY_SIZE,
    TOTAL_CHILD_RUNS_KEY,
    AzureStorageType,
    PromptflowEdition,
)
from promptflow.contracts.run_info import FlowRunInfo, RunInfo
from promptflow.contracts.run_info import Status
from promptflow.contracts.run_info import Status as PromptflowRunStatus
from promptflow.exceptions import ErrorResponse, ErrorTarget, RunInfoNotFoundInStorageError
from promptflow.runtime.utils import logger
from promptflow.storage.common import reconstruct_metrics_dict
from promptflow.storage.exceptions import (
    AzureStoragePackagesNotInstalledError,
    BlobAuthenticationError,
    BlobInitResponseError,
    BlobStorageInitError,
    BlobStorageWriteError,
    CannotCreateExistingRunInBlob,
    CannotCreateExistingRunInTable,
    CannotEndRunWithNonTerminatedStatus,
    CredentialMissing,
    FailedToCancelRun,
    FailedToCancelWithAnotherActiveRun,
    FailedToConvertRecordToRunInfo,
    FailedToCreateRun,
    FailedToEndRootRun,
    FailedToStartRun,
    FailedToStartRunAfterCreated,
    FlowIdMissing,
    GetFlowRunError,
    GetFlowRunResponseError,
    InvalidMLFlowTrackingUri,
    MLClientMissing,
    PartitionKeyMissingForRunQuery,
    RunNotFoundInTable,
    StorageHttpResponseError,
    StorageWriteForbidden,
    TableAuthenticationError,
    TableInitResponseError,
    TableStorageInitError,
    TableStorageWriteError,
    UnsupportedRunInfoTypeInBlob,
    to_string,
)
from promptflow.storage.run_storage import AbstractRunStorage
from promptflow.utils.dataclass_serializer import deserialize_flow_run_info, serialize
from promptflow.utils.logger_utils import bulk_logger, flow_logger
from promptflow.utils.retry_utils import retry
from promptflow.utils.timer import Timer
from promptflow.utils.utils import get_string_size, is_in_ci_pipeline

try:
    import mlflow
    from azure.core.credentials import AzureNamedKeyCredential
    from azure.core.exceptions import (
        ClientAuthenticationError,
        HttpResponseError,
        ResourceExistsError,
        ResourceNotFoundError,
    )
    from azure.data.tables import TableServiceClient
    from azure.storage.blob import BlobServiceClient
    from mlflow.entities.run import Run as MlflowRun
    from mlflow.entities.run_status import RunStatus as MlflowRunStatus
    from mlflow.exceptions import RestException
    from mlflow.protos.databricks_pb2 import BAD_REQUEST, RESOURCE_DOES_NOT_EXIST, ErrorCode
    from mlflow.tracking import MlflowClient
    from mlflow.utils.rest_utils import http_request
except ImportError as e:
    ex_message = str(e)
    msg = "Please install azure-related packages, currently got {customer_content}"
    logger.error(msg, extra={"customer_content": msg})
    raise AzureStoragePackagesNotInstalledError(
        message=msg.format(customer_content=ex_message), target=ErrorTarget.AZURE_RUN_STORAGE
    )


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


class AzureMLRunStorage(AbstractRunStorage):
    NODE_TABLE_NAME = "IntermediateRunRecords"
    FLOW_TABLE_NAME = "FlowRecords"
    BLOB_CONTAINER_NAME = "promptflow"
    NODE_BLOB_PATH_PREFIX = "NodeRunInfo"
    FLOW_BLOB_PATH_PREFIX = "FlowRunInfo"

    STORAGE_TYPE_PROPERTY = "storage_type"
    REQUIRED_PROPERTIES = {
        STORAGE_TYPE_PROPERTY,
        "PartitionKey",
        "RowKey",
        "max_property_bytes",
        "total_entity_bytes",
    }
    FLOW_RUN_INFO_PROPERTIES_TO_UPDATE = AbstractRunStorage.FLOW_RUN_INFO_PROPERTIES_TO_UPDATE | REQUIRED_PROPERTIES

    def __init__(self, storage_account_name: str, mlflow_tracking_uri: str, credential, ml_client) -> None:
        super().__init__(edition=PromptflowEdition.ENTERPRISE)
        if not credential:
            raise CredentialMissing(
                message="Failed to initialize AzureMLRunStorage: 'credential' cannot be empty.",
                target=ErrorTarget.AZURE_RUN_STORAGE,
            )
        if not ml_client:
            raise MLClientMissing(
                message="Failed to initialize AzureMLRunStorage: 'ml_client' cannot be empty.",
                target=ErrorTarget.AZURE_RUN_STORAGE,
            )
        self._storage_account_name = storage_account_name
        self.init_azure_table_service_client(credential, storage_account_name)
        self.init_azure_blob_service_client(credential, storage_account_name)
        self._mlflow_helper = MlflowHelper(mlflow_tracking_uri=mlflow_tracking_uri)
        self._ml_client = ml_client
        self._persisted_runs = set()

    def init_azure_table_service_client(self, credential, storage_account_name):
        """Initialize table service client"""
        endpoint = f"https://{storage_account_name}.table.core.windows.net"
        self.table_service_client = TableServiceClient(endpoint=endpoint, credential=credential)
        # test if current client has access to the storage table.
        try:
            self.node_table_client = self.table_service_client.create_table_if_not_exists(
                table_name=self.NODE_TABLE_NAME
            )
            self.flow_table_client = self.table_service_client.create_table_if_not_exists(
                table_name=self.FLOW_TABLE_NAME
            )
        except HttpResponseError as e:
            msg = str(e)
            if e.status_code == 403:
                auth_error_msg = (
                    "Failed to perform azure table operation due to invalid authentication. Please assign RBAC role "
                    "'Storage Table Data Contributor' to the service principal or client. "
                    "Original error: {customer_content}"
                )
                logger.error(auth_error_msg, extra={"customer_content": msg})
                raise TableAuthenticationError(
                    message=auth_error_msg.format(customer_content=msg),
                    target=ErrorTarget.AZURE_RUN_STORAGE,
                ) from e
            # For non 403 exception
            error_message = "Failed to get or create table. Get HttpResponseError: {customer_content}"
            logger.error(
                error_message,
                extra={"customer_content": msg},
            )
            raise TableInitResponseError(
                message=error_message.format(customer_content=msg),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e
        except Exception as e:
            msg = to_string(e)
            error_message = "Failed to get or create table, exception {customer_content}"
            logger.error(
                error_message,
                extra={"customer_content": msg},
            )
            raise TableStorageInitError(
                message=error_message.format(customer_content=msg),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e

        logger.info("Initialized table client for AzureMLRunTracker.")

    def init_azure_blob_service_client(self, credential, storage_account_name):
        """Initialize blob service client"""
        # AzureNameKeyCredential is supported from blob version 12.14.0, while currently we have blob version 12.13.0
        # due to azureml-mlflow package requirement. So we need extra process to make this work
        if isinstance(credential, AzureNamedKeyCredential):
            named_key = credential.named_key
            credential = {"account_name": named_key[0], "account_key": named_key[1]}

        blob_account_url = f"https://{storage_account_name}.blob.core.windows.net"
        blob_service_client = BlobServiceClient(blob_account_url, credential=credential)

        # test if current client has access to the storage blob.
        try:
            container = blob_service_client.get_container_client(self.BLOB_CONTAINER_NAME)
            # test blob data read access
            if not container.exists():
                blob_service_client.create_container(self.BLOB_CONTAINER_NAME)
            # test blob data write access
            container.set_container_metadata({"source": "promptflow"})
        except HttpResponseError as e:
            msg = str(e)
            if e.status_code == 403:
                auth_error_msg = (
                    "Failed to perform azure blob operation due to invalid authentication, please assign RBAC role "
                    "'Storage Blob Data Contributor' to the service principal or client. Original error: "
                    "{customer_content}"
                )
                logger.error(auth_error_msg, extra={"customer_content": msg})
                raise BlobAuthenticationError(
                    message=auth_error_msg.format(customer_content=msg),
                    target=ErrorTarget.AZURE_RUN_STORAGE,
                ) from e
            # For non 403 exception
            error_message = "Failed to perform azure blob operation due HttpResponseError: {customer_content}"
            logger.error(error_message, extra={"customer_content": msg})
            raise BlobInitResponseError(
                message=error_message.format(customer_content=msg),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e
        except Exception as e:
            msg = to_string(e)
            error_message = "Failed to get or create blob, exception {customer_content}"
            logger.error(
                error_message,
                extra={"customer_content": msg},
            )
            raise BlobStorageInitError(
                message=error_message.format(customer_content=msg),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e

        self.blob_service_client = blob_service_client
        logger.info("Initialized blob service client for AzureMLRunTracker.")

    def refine_the_run_record(self, run_records, properties=None):
        """Refine and persist the run record.

        1. Validate the max property size and overall size of record.
        2. Mark the storage type to table if it's not oversize, otherwise blob.
        """
        max_property_size = run_records.max_property_bytes
        total_entity_size = run_records.total_entity_bytes

        # oversize if single property size > 64 KB or total size > 1 MB
        # because the property size and total entity size are calculated in utf-8 format,
        # and the string will be transformed to utf-16 string when getting uploaded to remote azure table,
        # so the real limit should be set as half of the "TABLE_LIMIT_PROPERTY_SIZE" and "TABLE_LIMIT_ENTITY_SIZE"
        is_oversize = (
            max_property_size > TABLE_LIMIT_PROPERTY_SIZE / 2 or total_entity_size > TABLE_LIMIT_ENTITY_SIZE / 2
        )
        run_records.storage_type = AzureStorageType.BLOB if is_oversize else AzureStorageType.TABLE

        record_dict = run_records.__dict__
        if properties:
            return {k: record_dict[k] for k in properties}
        return record_dict

    def persist_node_run(self, run_info: RunInfo):
        """Persist node run record to remote storage

        - If the record is not oversize:
            - Persist full data to table

        - If the record is oversize:
            - Persist full data to blob
            - And persist partial data without run_info to table
        """
        with Timer(flow_logger, "Persist node info for run " + run_info.run_id):
            record_dict = self.refine_the_run_record(IntermediateRunRecords.from_run_info(run_info))
            if record_dict[self.STORAGE_TYPE_PROPERTY] == AzureStorageType.TABLE:
                # full record is persisted to table
                self._write_azure_table(
                    record_dict=record_dict, table_operation_method=self.node_table_client.create_entity
                )
            else:
                # full run_info is persisted to blob
                blob_path = f"{self.NODE_BLOB_PATH_PREFIX}/{record_dict['PartitionKey']}/{record_dict['RowKey']}.json"
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.BLOB_CONTAINER_NAME, blob=blob_path
                )
                data = record_dict["run_info"]
                self._write_azure_blob(data, blob_client.upload_blob)

                # partial record with blob path is persisted to table
                record_dict["run_info"] = self.get_relative_path_in_blob(
                    run_info_type="node", partition_key=record_dict["PartitionKey"], row_key=record_dict["RowKey"]
                )
                self._write_azure_table(
                    record_dict=record_dict, table_operation_method=self.node_table_client.create_entity
                )

    def persist_flow_run(self, run_info: FlowRunInfo):
        """Persist flow run record to remote storage

        - If the record is not oversize:
            - Persist full data to table

        - If the record is oversize:
            - Persist full data to blob
            - And persist partial data without run_info to table
        """
        self._create_or_update_flow_run_info(run_info=run_info)

    def update_flow_run_info(self, run_info: FlowRunInfo):
        """Update the following flow run info fields: status, end_time, run_info

        - If the record is not oversize:
            - Persist full data to table

        - If the record is oversize:
            - Persist full data to blob
            - And persist partial data without run_info to table
        """
        # Update run history status and metrics
        if Status.is_terminated(run_info.status) and run_info.upload_metrics:
            self._upload_metrics(run_info)
            self._update_run_history_properties(run_info)
            # end the root flow run that was created in azure machine learning workspace
            self._end_aml_root_run(run_info=run_info)

        self._create_or_update_flow_run_info(run_info=run_info)

    def persist_status_summary(self, metrics: dict, flow_run_id: str):
        self._mlflow_helper.persist_status_summary(metrics=metrics, flow_run_id=flow_run_id)

    def _update_run_history_properties(self, run_info: FlowRunInfo):
        self._mlflow_helper.update_run_history_properties(run_info=run_info)

    def _upload_metrics(self, run_info: FlowRunInfo):
        self._mlflow_helper.upload_metrics_to_run_history(run_info=run_info)

    def _create_or_update_flow_run_info(self, run_info: FlowRunInfo):
        with Timer(flow_logger, "Create/update flow info for run " + run_info.run_id):
            """Create or update a flow run info."""
            # default parameters for create operation
            properties = self.FLOW_RUN_INFO_PROPERTIES_TO_UPDATE
            table_operation_method = self.flow_table_client.upsert_entity
            overwrite_blob = True

            # start to create or update the storage
            record_dict = self.refine_the_run_record(FlowRecords.from_run_info(run_info), properties=properties)
            if record_dict[self.STORAGE_TYPE_PROPERTY] == AzureStorageType.TABLE:
                # full record is persisted to table
                self._write_azure_table(record_dict=record_dict, table_operation_method=table_operation_method)
            else:
                # full record is persisted to blob
                blob_path = f"{self.FLOW_BLOB_PATH_PREFIX}/{record_dict['PartitionKey']}/{record_dict['RowKey']}.json"
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.BLOB_CONTAINER_NAME, blob=blob_path
                )
                data = record_dict["run_info"]
                self._write_azure_blob(data, blob_client.upload_blob, overwrite=overwrite_blob)

                # partial record with blob path is persisted to table
                record_dict["run_info"] = self.get_relative_path_in_blob(
                    run_info_type="flow", partition_key=record_dict["PartitionKey"], row_key=record_dict["RowKey"]
                )
                self._write_azure_table(record_dict=record_dict, table_operation_method=table_operation_method)

    def _write_azure_table(self, record_dict: dict, table_operation_method: Callable):
        """Try write azure table and handle the exceptions"""
        # note all auth related error are already handled in the constructor
        partition_key = record_dict["PartitionKey"]
        row_key = record_dict["RowKey"]

        try:
            table_operation_method(entity=record_dict)
        except ResourceNotFoundError as e:
            original_msg = str(e)
            detailed_message = f"partition key {partition_key!r}, row key {row_key!r}, Original error: {original_msg}"
            refined_error_msg = "Failed to update record in azure table with {customer_content}"
            logger.error(refined_error_msg, extra={"customer_content": detailed_message})
            raise RunNotFoundInTable(
                message=refined_error_msg.format(customer_content=detailed_message),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e
        except ResourceExistsError as e:
            original_msg = str(e)
            detailed_message = f"partition key {partition_key!r}, row key {row_key!r}, Original error: {original_msg}"
            refined_error_msg = (
                "Failed to create record in azure table with {customer_content}. "
                "May indicate executor receives a new request with an old run id that was processed before. "
            )
            logger.error(refined_error_msg, extra={"customer_content": detailed_message})
            raise CannotCreateExistingRunInTable(
                message=refined_error_msg.format(customer_content=detailed_message),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e
        except HttpResponseError as e:
            original_msg = to_string(e)
            detailed_message = f"partition key {partition_key!r}, row key {row_key!r}, Original error: {original_msg}"
            refined_error_msg = "Failed to perform azure table operations with {customer_content}."
            logger.error(refined_error_msg, extra={"customer_content": detailed_message})
            if e.status_code == 403:
                raise StorageWriteForbidden(
                    message=refined_error_msg.format(customer_content=detailed_message),
                    target=ErrorTarget.AZURE_RUN_STORAGE,
                ) from e
            raise StorageHttpResponseError(
                message=refined_error_msg.format(customer_content=detailed_message),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e
        except Exception as e:
            original_msg = str(e)
            detailed_message = f"partition key {partition_key!r}, row key {row_key!r}, Original error: {original_msg}"
            refined_error_msg = "Failed to perform azure table operations with {customer_content}."
            logger.error(refined_error_msg, extra={"customer_content": detailed_message})
            raise TableStorageWriteError(
                message=refined_error_msg.format(customer_content=detailed_message),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e

    def _write_azure_blob(self, blob_entity: str, blob_operation_method: Callable, overwrite=False):
        """Try write azure blob and handle the exceptions"""
        # note all auth related error are already handled in the constructor
        try:
            blob_operation_method(blob_entity, overwrite=overwrite)
        except ResourceExistsError as e:
            original_msg = str(e)
            detailed_message = f"overwrite flag '{overwrite}', Original error: {original_msg}"
            refined_error_msg = (
                "Failed to upload run info to blob with {customer_content}. If the flag is set to False, "
                "it may indicate the upload logic is trying to create a new blob with an existing name. "
            )
            logger.error(refined_error_msg, extra={"customer_content": detailed_message})
            raise CannotCreateExistingRunInBlob(
                message=refined_error_msg.format(customer_content=detailed_message),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e
        except Exception as e:
            original_msg = to_string(e)
            refined_error_msg = "Failed to upload run info to blob. Original error: {customer_content}"
            logger.error(refined_error_msg, extra={"customer_content": original_msg})
            raise BlobStorageWriteError(
                message=refined_error_msg.format(customer_content=original_msg),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e

    def get_flow_run(self, run_id: str, flow_id=None) -> FlowRunInfo:
        if flow_id is None:
            raise FlowIdMissing(message="Cannot get flow run without flow id.", target=ErrorTarget.AZURE_RUN_STORAGE)
        try:
            record = self.flow_table_client.get_entity(partition_key=flow_id, row_key=run_id)

            if record.get("run_info") is None:
                # Root flow run is created by upper-stream service before executor,
                # in which run_info is not set.
                return self._convert_run_record_without_run_info(record)

            if record.get("storage_type") == AzureStorageType.TABLE:
                run_info_data = record["run_info"]
                return deserialize_flow_run_info(json.loads(run_info_data))

            # read run info to get blob path
            run_info = json.loads(record["run_info"])
            blob_client = self.blob_service_client.get_blob_client(
                container=run_info["container"], blob=run_info["relative_path"]
            )
            run_info_data = json.loads(blob_client.download_blob().readall())
            return deserialize_flow_run_info(run_info_data)

        except HttpResponseError as error:
            original_msg = str(error)
            detailed_message = f"Run id: {run_id}, flow id: {flow_id}, Original error: {original_msg}"
            if error.status_code == 404:
                refined_error_msg = "Flow run info not found. {customer_content}"
                logger.error(refined_error_msg, extra={"customer_content": detailed_message})
                raise RunInfoNotFoundInStorageError(
                    message=refined_error_msg.format(customer_content=detailed_message),
                    target=ErrorTarget.AZURE_RUN_STORAGE,
                    storage_type=type(self),
                ) from error
            else:
                refined_error_msg = "Failed to get flow run info due to http error. {customer_content}"
                logger.error(refined_error_msg, extra={"customer_content": detailed_message})
                raise GetFlowRunResponseError(
                    message=refined_error_msg.format(customer_content=detailed_message),
                    target=ErrorTarget.AZURE_RUN_STORAGE,
                    storage_type=type(self),
                ) from error
        except Exception as error:
            original_msg = to_string(error)
            detailed_message = f"Run id: {run_id}, flow id: {flow_id}, Original error: {original_msg}"
            refined_error_msg = "Failed to get flow run info due to exception. {customer_content}"
            logger.error(refined_error_msg, extra={"customer_content": detailed_message})
            raise GetFlowRunError(
                message=refined_error_msg.format(customer_content=detailed_message),
                target=ErrorTarget.AZURE_RUN_STORAGE,
                storage_type=type(self),
            ) from error

    def _convert_entity_to_run_info(self, record) -> Dict:
        try:
            if record.get("run_info") is None:
                # Root flow run is created by upper-stream service before executor,
                # in which run_info is not set.
                return vars(self._convert_run_record_without_run_info(record))

            if record.get("storage_type") == AzureStorageType.TABLE:
                run_info_data = record["run_info"]
                return json.loads(run_info_data)

            # read run info to get blob path
            run_info = json.loads(record["run_info"])
            container = run_info.get("container")
            blob = run_info.get("relative_path")
            blob_client = self.blob_service_client.get_blob_client(container=container, blob=blob)
            run_info_data = json.loads(blob_client.download_blob().readall())
            return run_info_data
        except Exception as error:
            error_message = to_string(error)
            content = f"record={record}, error_message={error_message}"
            refined_error_msg = "Failed to convert record to run info dict. {customer_content}"

            logger.error(refined_error_msg, extra={"customer_content": content})
            raise FailedToConvertRecordToRunInfo(
                refined_error_msg.format(customer_content=content), target=ErrorTarget.AZURE_RUN_STORAGE
            ) from error

    def get_run_info_by_partition_key(self, partition_key=None, is_node_run: bool = False) -> List[Dict]:
        if partition_key is None:
            raise PartitionKeyMissingForRunQuery(
                message="Cannot get flow run list without partition key.", target=ErrorTarget.AZURE_RUN_STORAGE
            )
        try:
            # Query the table using the partition key
            query_filter = "PartitionKey eq '{}'".format(partition_key)
            if is_node_run:
                # For Node run query in "IntermediateRunRecords"
                records = self.node_table_client.query_entities(query_filter=query_filter)
            else:
                # Flow run query in "FlowRecords"
                records = self.flow_table_client.query_entities(query_filter=query_filter)
        except Exception as error:
            error_message = to_string(error)
            content = f"Partition_key={partition_key}, error_message={error_message}"
            refined_error_msg = "Failed to get run info with partition key. {customer_content}"

            logger.error(refined_error_msg, extra={"customer_content": content})
            raise RunInfoNotFoundInStorageError(
                refined_error_msg.format(customer_content=content),
                target=ErrorTarget.AZURE_RUN_STORAGE,
                storage_type=type(self),
            ) from error

        runInfo = [self._convert_entity_to_run_info(record) for record in records]
        return runInfo

    def get_relative_path_in_blob(self, run_info_type: str, partition_key: str, row_key: str) -> str:
        """Get a json string that indicates the container and relative path in remote blob"""
        if run_info_type == "flow":
            path_prefix = f"{self.FLOW_BLOB_PATH_PREFIX}"
        elif run_info_type == "node":
            path_prefix = f"{self.NODE_BLOB_PATH_PREFIX}"
        else:
            raise UnsupportedRunInfoTypeInBlob(
                message=f"Unknown run info type, must be one of ['flow', 'node'], got {run_info_type!r}.",
                target=ErrorTarget.AZURE_RUN_STORAGE,
            )

        blob_path_info = {
            "container": self.BLOB_CONTAINER_NAME,
            "relative_path": f"{path_prefix}/{partition_key}/{row_key}.json",
        }
        return json.dumps(blob_path_info)

    @staticmethod
    def _convert_run_record_without_run_info(record: Dict) -> FlowRunInfo:
        try:
            tags = json.loads(record.get("tags", "{}"))
        except json.JSONDecodeError:
            tags = {}
        return FlowRunInfo(
            run_id=record.get("RowKey"),
            status=Status(record.get("status")),
            error=None,
            inputs=None,
            output=None,
            metrics=None,
            request=None,
            parent_run_id="",
            root_run_id=record.get("root_run_id"),
            source_run_id=None,
            flow_id=record.get("PartitionKey"),
            start_time=None,
            end_time=None,
            index=None,
            name=record.get("name", ""),
            tags=tags,
            description=record.get("description", ""),
        )

    def _start_aml_root_run(self, run_id: str) -> None:
        """Update root run that gets created by MT to running status"""
        self._mlflow_helper.start_run(run_id=run_id, create_if_not_exist=True)

    def _end_aml_root_run(self, run_info: FlowRunInfo, ex: Exception = None) -> None:
        """Update root run to end status"""
        # if error detected, write error info to run history
        error_response = self._get_error_response_dict(run_info, ex=ex)
        if error_response:
            current_run = mlflow.active_run()
            if current_run:
                self._mlflow_helper.write_error_message(mlflow_run=current_run, error_response=error_response)
            else:
                logger.warning("No active run exists. Skip updating error response")

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


class MlflowHelper:
    ERROR_EVENT_NAME = "Microsoft.MachineLearning.Run.Error"
    ERROR_MESSAGE_SET_MULTIPLE_TERMINAL_STATUS = "Cannot set run to multiple terminal states"
    RUN_HISTORY_TOTAL_TOKENS_PROPERTY_NAME = "azureml.promptflow.total_tokens"
    RUN_HISTORY_TOTAL_CHILD_RUNS_PROPERTY_NAME = "azureml.promptflow.total_child_runs"

    def __init__(self, mlflow_tracking_uri):
        """Set mlflow tracking uri to target uri"""
        self.enable_usage_in_ci_pipeline_if_needed()
        if isinstance(mlflow_tracking_uri, str) and mlflow_tracking_uri.startswith("azureml:"):
            logger.info(f"Setting mlflow tracking uri to {mlflow_tracking_uri!r}")
            mlflow.set_tracking_uri(mlflow_tracking_uri)
        else:
            content = f"{mlflow_tracking_uri!r} with type {type(mlflow_tracking_uri)!r}"
            refined_error_msg = (
                "Mlflow tracking uri must be a string that starts with 'azureml:', " "got {customer_content}"
            )
            logger.error(refined_error_msg, extra={"customer_content": content})
            raise InvalidMLFlowTrackingUri(
                message=refined_error_msg.format(customer_content=content), target=ErrorTarget.AZURE_RUN_STORAGE
            )

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
            msg = to_string(e)
            if (
                create_if_not_exist
                and isinstance(e, RestException)
                and e.error_code == ErrorCode.Name(RESOURCE_DOES_NOT_EXIST)
            ):
                logger.warning(f"Run {run_id!r} not found, will create a new run with this run id.")
                self.create_run(run_id=run_id)
                return
            content = f"root run: {run_id!r}, exception: {msg}"
            refined_error_msg = "Failed to start root run with {customer_content}"
            logger.error(refined_error_msg, extra={"customer_content": content})
            raise FailedToStartRun(
                message=refined_error_msg.format(customer_content=content),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            ) from e

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
                    msg = to_string(e)
                    content = f"run_id: {run_id!r}, exception: {msg}"
                    refined_error_msg = "A new run is created but failed to start {customer_content}"
                    logger.error(refined_error_msg, extra={"customer_content": content})
                    raise FailedToStartRunAfterCreated(
                        message=refined_error_msg.format(customer_content=content),
                        target=ErrorTarget.AZURE_RUN_STORAGE,
                    )
        else:
            content = f"run_id: {run_id!r}, response_text: {response.text}"
            refined_error_msg = "Failed to create run {customer_content}"
            logger.error(refined_error_msg, extra={"customer_content": content})
            raise FailedToCreateRun(
                message=refined_error_msg.format(customer_content=content),
                target=ErrorTarget.AZURE_RUN_STORAGE,
            )

    def get_run(self, run_id: str):
        return mlflow.get_run(run_id=run_id)

    def end_run(self, run_id: str, status: str):
        """Update root run to end status"""
        if status not in RunStatusMapping:
            raise CannotEndRunWithNonTerminatedStatus(
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
            msg = to_string(e)
            content = f"run_id: {run_id!r}, exception: {msg}"
            refined_error_msg = "Failed to end root run {customer_content}"
            logger.error(refined_error_msg, extra={"customer_content": content})
            raise FailedToEndRootRun(
                message=refined_error_msg.format(customer_content=content), target=ErrorTarget.AZURE_RUN_STORAGE
            ) from e

    def active_run(self):
        """Get current active run"""
        return mlflow.active_run()

    def cancel_run(self, run_id: str):
        """Cancel a specific run"""
        logger.info(f"Getting current active run {run_id!r}...")
        current_run = mlflow.active_run()
        if current_run and current_run.info.run_id != run_id:
            message = f"Failed to cancel run {run_id!r} since there is another active run {current_run.info.run_id!r}."
            raise FailedToCancelWithAnotherActiveRun(
                message=message,
                target=ErrorTarget.AZURE_RUN_STORAGE,
            )
        try:
            logger.info(f"Resuming existing run {run_id!r}...")
            mlflow.start_run(run_id=run_id)
            logger.info(f"Cancelling run {run_id!r}...")
            mlflow.end_run(status=MlflowRunStatus.to_string(MlflowRunStatus.KILLED))
        except Exception as e:
            msg = to_string(e)
            if (
                isinstance(e, RestException)
                and e.error_code == ErrorCode.Name(BAD_REQUEST)
                and self.ERROR_MESSAGE_SET_MULTIPLE_TERMINAL_STATUS in msg
            ):
                logger.warning(f"Run {run_id!r} is already in terminal states, skipped cancel request.")
                return

            content = f"run_id: {run_id!r}, exception: {msg}"
            refined_error_msg = "Failed to cancel root run {customer_content}"
            logger.error(refined_error_msg, extra={"customer_content": content})
            raise FailedToCancelRun(
                message=refined_error_msg.format(customer_content=content), target=ErrorTarget.AZURE_RUN_STORAGE
            ) from e

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
            self.RUN_HISTORY_TOTAL_TOKENS_PROPERTY_NAME: run_info.system_metrics.get("total_tokens", 0),
            self.RUN_HISTORY_TOTAL_CHILD_RUNS_PROPERTY_NAME: run_info.system_metrics.get(TOTAL_CHILD_RUNS_KEY, 0),
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
                    logger.warning(f"Failed to upload metrics to workspace: {to_string(e)}")
        elif metrics is not None:
            logger.warning(
                (f"Metrics should be a dict but got a {type(metrics)!r} with content " "{customer_dimension}"),
                extra={"customer_dimension": str(metrics)},
            )

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
                    logger.warning(f"Failed to upload status summary metrics to workspace: {to_string(e)}")
        elif metrics is not None:
            logger.warning(f"Metrics should be a dict but got a {type(metrics)!r} with content {metrics!r}")


@dataclass
class IntermediateRunRecords:
    PartitionKey: str  # FlowRunId
    RowKey: str  # FlowRunId:StepRunId
    parent_run_id: str  # FlowRunId:ChildFlowRunId
    run_info: str
    start_time: datetime
    end_time: datetime
    status: str
    storage_type: str
    max_property_bytes: int
    total_entity_bytes: int

    @staticmethod
    def from_run_info(run_info: RunInfo) -> "IntermediateRunRecords":
        param_list = [
            run_info.flow_run_id,
            run_info.run_id,
            run_info.parent_run_id,
            json.dumps(serialize(run_info)),
            run_info.start_time,
            run_info.end_time,
            run_info.status.value,
        ]
        # calculate max property size and total row size
        value_size_list = [get_string_size(str(item)) for item in param_list]
        max_property_size = max(value_size_list)
        total_entity_size = sum(value_size_list)

        return IntermediateRunRecords(
            *param_list,
            AzureStorageType.LOCAL,
            max_property_size,
            total_entity_size,
        )


@dataclass
class FlowRecords:
    PartitionKey: str  # FlowId
    RowKey: str  # FlowRunId:ChildFlowRunId
    source_run_id: str
    parent_run_id: str
    root_run_id: str
    run_info: str
    start_time: datetime
    end_time: datetime
    name: str
    description: str
    status: str
    tags: str
    storage_type: str
    max_property_bytes: int
    total_entity_bytes: int

    @staticmethod
    def from_run_info(run_info: FlowRunInfo) -> "FlowRecords":
        param_list = [
            run_info.flow_id,
            run_info.run_id,
            run_info.source_run_id,
            run_info.parent_run_id,
            run_info.root_run_id,
            json.dumps(serialize(run_info)),
            run_info.start_time,
            run_info.end_time,
            run_info.name,
            run_info.description,
            run_info.status.value,
            json.dumps(run_info.tags),
        ]

        # calculate max property size and total row size
        value_size_list = [get_string_size(str(item)) for item in param_list]
        max_property_size = max(value_size_list)
        total_entity_size = sum(value_size_list)

        return FlowRecords(
            *param_list,
            AzureStorageType.LOCAL,
            max_property_size,
            total_entity_size,
        )

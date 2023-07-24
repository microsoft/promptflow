import json
from dataclasses import dataclass, field
from datetime import datetime

from promptflow._constants import PromptflowEdition
from promptflow.contracts.run_info import FlowRunInfo, RunInfo, Status
from promptflow.exceptions import ErrorTarget, RunInfoNotFoundInStorageError, SystemErrorException
from promptflow.storage.common import reconstruct_metrics_dict
from promptflow.storage.sqlite_client import INDEX, PRIMARY_KEY, NotFoundException, SqliteClient
from promptflow.utils.dataclass_serializer import deserialize_flow_run_info, deserialize_node_run_info
from promptflow.utils.logger_utils import flow_logger

from ..utils.dataclass_serializer import serialize
from .run_storage import AbstractRunStorage


class LocalRunStorage(AbstractRunStorage):
    @classmethod
    def create_tables(cls, db_folder_path: str, db_name: str, test_mode: bool = False):
        """Create db tables if not exists. If table exists, check if columns are consistent with associated class.

        Note that this method involves disk io, it is not safe to be invoked concurrently.
        """
        # Create table for local run records.
        SqliteClient.create_table_if_not_exists(db_folder_path, db_name, LocalRunRecords, test_mode)

        # Create table  for local flow records.
        SqliteClient.create_table_if_not_exists(db_folder_path, db_name, LocalFlowRecords, test_mode)

        # Create table for local metrics.
        SqliteClient.create_table_if_not_exists(db_folder_path, db_name, class_=LocalMetrics, in_memory=test_mode)

    def __init__(self, db_folder_path: str, db_name: str, test_mode: bool = False):
        """Create table clients and create db tables if not exists.

        This method should be invoked after create_tables.
        After invoking create_tables, this method is safe to be invoked concurrently; otherwise it is not.
        """
        self.node_table_client = SqliteClient(
            db_folder_path, db_name, class_=LocalRunRecords, in_memory=test_mode
        )  # For test mode, create db in memory.

        self.flow_table_client = SqliteClient(
            db_folder_path, db_name, class_=LocalFlowRecords, in_memory=test_mode
        )  # For test mode, create db in memory.

        self.metrics_client = SqliteClient(
            db_folder_path, db_name, class_=LocalMetrics, in_memory=test_mode
        )  # For test mode, create db in memory.

        super().__init__(edition=PromptflowEdition.COMMUNITY)

    def persist_node_run(self, run_info: RunInfo):
        run_records = LocalRunRecords.from_run_info(run_info)
        self.node_table_client.insert(run_records)

    def persist_flow_run(self, run_info: FlowRunInfo):
        flow_records = LocalFlowRecords.from_run_info(run_info)
        self.flow_table_client.upsert(flow_records)

    def get_node_run(self, run_id: str) -> RunInfo:
        run_record = self.node_table_client.get(run_id)
        return deserialize_node_run_info(json.loads(run_record.run_info))

    def get_flow_run(self, run_id: str, flow_id=None) -> FlowRunInfo:
        run_record = self._get_flow_run_record(run_id)
        if run_record.run_info:
            return deserialize_flow_run_info(json.loads(run_record.run_info))
        else:
            return self._convert_run_record_without_run_info(run_record)

    def update_flow_run_info(self, run_info: FlowRunInfo):
        """Update flow run records in storage.

        The new flow run record consists of fields in input run_info and existing flow run record.
        """
        if Status.is_terminated(run_info.status) and run_info.upload_metrics:
            self._upload_metrics(run_info.metrics, run_info.run_id, run_info.flow_id, run_info.parent_run_id)

        existing_flow_run = None
        try:
            existing_flow_run = self.flow_table_client.get(run_info.run_id)
        except NotFoundException:
            flow_logger.warning(f"No existing flow run found for {run_info.run_id}.")
        flow_records = LocalFlowRecords.from_run_info(run_info, existing_flow_run)
        self.flow_table_client.upsert(flow_records)

    def cancel_run(self, run_id: str):
        try:
            run_info = self.get_flow_run(run_id)
            if Status.is_terminated(run_info.status):
                flow_logger.warning(
                    f"Flow run {run_id} is already terminated with status {run_info.status}. \
                             No need to cancel."
                )
                return
            run_info.status = Status.Canceled
            run_info.end_time = datetime.utcnow()
            self.update_flow_run_info(run_info)
        except Exception as e:
            raise SystemErrorException(
                f"Failed to cancel run {run_id}. Exception: {e}",
                target=ErrorTarget.RUN_STORAGE,
                error=e,
            )

    def get_run_status(self, run_id: str) -> str:
        """Get run status from flow run records's status, not from run info."""
        run_status = None
        try:
            run_record = self._get_flow_run_record(run_id)
            return run_record.status
        except RunInfoNotFoundInStorageError as e:
            flow_logger.warning(f"Failed to get run status of run {run_id!r} due to run not found: {str(e)}")
        return run_status

    def persist_status_summary(self, metrics: dict, flow_run_id: str):
        # Do nothing in local storage
        return

    def _upload_metrics(self, metrics: dict, flow_run_id: str, flow_id: str, parent_run_id: str):
        if metrics is None:
            flow_logger.warning(f"Metrics is None. flow run id: {flow_run_id}, flow id: {flow_id}")
            return

        new_metrics = reconstruct_metrics_dict(metrics)
        local_metrics = LocalMetrics.from_metrics(new_metrics, flow_run_id, flow_id, parent_run_id)
        self.metrics_client.insert(local_metrics)

    def _get_flow_run_record(self, run_id: str) -> "LocalFlowRecords":
        try:
            return self.flow_table_client.get(run_id)
        except NotFoundException as ex:
            raise RunInfoNotFoundInStorageError(
                f"Flow run not found. run id: {run_id}",
                target=ErrorTarget.RUN_STORAGE,
                storage_type=type(self),
            ) from ex

    @staticmethod
    def _convert_run_record_without_run_info(record: "LocalFlowRecords") -> FlowRunInfo:
        try:
            tags = json.loads(record.tags)
        except json.JSONDecodeError:
            tags = {}
        return FlowRunInfo(
            run_id=record.run_id,
            status=Status(record.status),
            error=None,
            inputs=None,
            output=None,
            metrics=None,
            request=None,
            parent_run_id="",
            root_run_id=record.root_run_id,
            source_run_id=None,
            flow_id=record.flow_id,
            start_time=record.start_time,
            end_time=None,
            index=None,
            name=record.name,
            tags=tags,
            description=record.description,
        )


@dataclass
class LocalRunRecords:
    flow_run_id: str = field(metadata={INDEX: True})  # FlowRunId
    run_id: str = field(metadata={PRIMARY_KEY: True})  # FlowRunId:StepRunId
    parent_run_id: str  # FlowRunId:ChildFlowRunId
    run_info: str
    start_time: datetime
    end_time: datetime
    status: str

    @staticmethod
    def from_run_info(run_info: RunInfo) -> "LocalRunRecords":
        return LocalRunRecords(
            run_info.flow_run_id,
            run_info.run_id,
            run_info.parent_run_id,
            json.dumps(serialize(run_info)),
            run_info.start_time,
            run_info.end_time,
            run_info.status.value,
        )


@dataclass
class LocalFlowRecords:
    flow_id: str = field(metadata={INDEX: True})  # FlowId
    run_id: str = field(metadata={PRIMARY_KEY: True})  # FlowRunId:ChildFlowRunId
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
    run_type: str
    bulk_test_id: str
    created_date: datetime
    flow_graph: str
    flow_graph_layout: str

    @staticmethod
    def from_run_info(run_info: FlowRunInfo, existing_flow_record: "LocalFlowRecords" = None) -> "LocalFlowRecords":
        return LocalFlowRecords(
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
            existing_flow_record.run_type if existing_flow_record else None,
            existing_flow_record.bulk_test_id if existing_flow_record else None,
            existing_flow_record.created_date if existing_flow_record else None,
            existing_flow_record.flow_graph if existing_flow_record else None,
            existing_flow_record.flow_graph_layout if existing_flow_record else None,
        )


@dataclass
class LocalMetrics:
    flow_run_id: str = field(metadata={PRIMARY_KEY: True})
    flow_id: str
    parent_run_id: str = field(metadata={INDEX: True})
    metrics: str = None

    def to_metrics(self) -> dict:
        return json.loads(self.metrics)

    @staticmethod
    def from_metrics(metrics: dict, flow_run_id: str, flow_id: str, parent_run_id: str) -> "LocalMetrics":
        return LocalMetrics(
            flow_run_id=flow_run_id, flow_id=flow_id, parent_run_id=parent_run_id, metrics=json.dumps(metrics)
        )

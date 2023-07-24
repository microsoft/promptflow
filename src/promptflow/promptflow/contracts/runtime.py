import json
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Type, TypeVar, Union

from ..utils._runtime_contract_util import normalize_dict_keys_camel_to_snake
from ..utils.dataclass_serializer import serialize
from .azure_storage_setting import AzureStorageSetting
from .error_codes import (
    FlowRequestDeserializeError,
    InvalidFlowSourceType,
    InvalidRunMode,
    MissingEvalFlowId,
    SubmissionDataDeserializeError,
)
from .flow import BatchFlowRequest, EvalRequest, NodesRequest
from .run_mode import RunMode

T = TypeVar("T")


@dataclass
class BatchDataInput:
    data_uri: str = None

    @staticmethod
    def deserialize(data: dict) -> "BatchDataInput":
        data = normalize_dict_keys_camel_to_snake(data)
        return BatchDataInput(
            data_uri=data.get("data_uri", ""),
        )


@dataclass
class CreatedBy:
    user_object_id: str = None
    user_tenant_id: str = None
    user_name: str = None

    @staticmethod
    def deserialize(data: dict) -> "CreatedBy":
        data = normalize_dict_keys_camel_to_snake(data)
        return CreatedBy(
            user_object_id=data.get("user_object_id", ""),
            user_tenant_id=data.get("user_tenant_id", ""),
            user_name=data.get("user_name", ""),
        )


@dataclass
class AzureFileShareInfo:
    working_dir: str
    sas_url: Optional[str] = None

    @staticmethod
    def deserialize(data: dict):
        return AzureFileShareInfo(working_dir=data.get("working_dir", ""), sas_url=data.get("sas_url", ""))


@dataclass
class SnapshotInfo:
    snapshot_id: str


class FlowSourceType(int, Enum):
    AzureFileShare = 0
    Snapshot = 1


@dataclass
class FlowSource:
    flow_source_type: FlowSourceType
    flow_source_info: Union[AzureFileShareInfo, SnapshotInfo]
    flow_dag_file: str

    @staticmethod
    def deserialize(data: dict) -> "FlowSource":
        flow_source = FlowSource(
            flow_source_type=FlowSourceType(data.get("flow_source_type", FlowSourceType.AzureFileShare)),
            flow_source_info=data.get("flow_source_info", {}),
            flow_dag_file=data.get("flow_dag_file", ""),
        )

        flow_source_info = flow_source.flow_source_info

        if flow_source.flow_source_type == FlowSourceType.AzureFileShare:
            flow_source.flow_source_info = AzureFileShareInfo.deserialize(flow_source_info)
        elif flow_source.flow_source_type == FlowSourceType.Snapshot:
            flow_source.flow_source_info = SnapshotInfo(snapshot_id=flow_source_info.get("snapshot_id", ""))
        else:
            raise InvalidFlowSourceType(
                message_format="Invalid flow_source_type value: {flow_source_type}",
                flow_source_type=flow_source.flow_source_type,
            )

        return flow_source


@dataclass
class MetaV2Request:
    tools: Dict[str, Dict]
    flow_source_info: AzureFileShareInfo

    @staticmethod
    def deserialize(data: dict):
        return MetaV2Request(
            tools=data.get("tools", {}),
            flow_source_info=AzureFileShareInfo.deserialize(data.get("flow_source_info", {})),
        )


@dataclass
class SubmissionRequestBaseV2:
    # Flow execution required fields
    flow_id: str
    flow_run_id: str
    flow_source: FlowSource
    connections: Dict[str, Any]

    # Runtime fields, could be optional
    log_path: Optional[str] = None
    environment_variables: Optional[Dict[str, str]] = None
    app_insights_instrumentation_key: Optional[str] = None

    @classmethod
    def deserialize(cls, data: dict):
        return cls(
            flow_id=data.get("flow_id", ""),
            flow_run_id=data.get("flow_run_id", ""),
            flow_source=FlowSource.deserialize(data.get("flow_source", {})),
            connections=data.get("connections", {}),
            log_path=data.get("log_path", ""),
            environment_variables=data.get("environment_variables", {}),
            app_insights_instrumentation_key=data.get("app_insights_instrumentation_key"),
        )

    def desensitize_to_json(self) -> str:
        """This function is used to desensitize request for logging."""
        ignored_keys = ["connections"]
        place_holder = "**data_scrubbed**"
        data = asdict(
            self, dict_factory=lambda x: {k: place_holder if k in ignored_keys else serialize(v) for (k, v) in x if v}
        )
        return json.dumps(data)

    def get_run_mode(self):
        raise NotImplementedError(f"Request type {self.__class__.__name__} is not implemented.")


@dataclass
class FlowRequestV2(SubmissionRequestBaseV2):
    inputs: Mapping[str, Any] = None

    @classmethod
    def deserialize(cls, data: dict) -> "FlowRequestV2":
        req = super().deserialize(data)
        req.inputs = data.get("inputs", {})
        return req

    def get_run_mode(self):
        return RunMode.Flow


@dataclass
class BulkRunRequestV2(SubmissionRequestBaseV2):
    data_inputs: Mapping[str, str] = None
    inputs_mapping: Mapping[str, str] = None
    azure_storage_setting: AzureStorageSetting = None

    def get_run_mode(self):
        return RunMode.BulkTest

    @classmethod
    def deserialize(cls, data: dict) -> "BulkRunRequestV2":
        req = super().deserialize(data)
        req.data_inputs = data.get("data_inputs", {})
        req.inputs_mapping = data.get("inputs_mapping", {})
        req.azure_storage_setting = AzureStorageSetting.deserialize(data.get("azure_storage_setting", {}))
        return req


@dataclass
class SingleNodeRequestV2(SubmissionRequestBaseV2):
    node_name: str = None
    inputs: Mapping[str, Any] = None

    @classmethod
    def deserialize(cls, data: dict) -> "SingleNodeRequestV2":
        req = super().deserialize(data)
        req.node_name = data.get("node_name", "")
        req.inputs = data.get("inputs", {})
        return req

    def get_run_mode(self):
        return RunMode.SingleNode


@dataclass
class SubmitFlowRequest:
    """Request send from MT to runtime to run a flow."""

    flow_id: str
    flow_run_id: str = ""
    source_flow_run_id: str = ""
    submission_data: Union[BatchFlowRequest, EvalRequest, NodesRequest] = None
    flow_source: Optional[FlowSource] = None
    run_mode: RunMode = RunMode.Flow
    created_by: CreatedBy = None
    workspace_msi_token_for_storage_resource: str = None
    batch_data_input: BatchDataInput = None
    bulk_test_data_input: BatchDataInput = None
    environment_variables: Dict[str, Any] = None
    run_id_to_log_path: Dict[str, str] = None
    app_insights_instrumentation_key: str = None
    azure_storage_setting: AzureStorageSetting = None

    def _normalize_submission_data(self):
        """Normalize submission data to make sure it is in the right format."""
        if isinstance(self.submission_data, str):
            # submission data is a json string
            try:
                self.submission_data = json.loads(self.submission_data)
            except Exception as ex:
                raise SubmissionDataDeserializeError(
                    message_format="Failed to deserialize submission data due to {exception}.", exception=str(ex)
                ) from ex

        if not isinstance(self.submission_data, dict):
            return

        # normalize submission data dict
        data = self.submission_data

        # Ensure flow id is set
        if "flow" in data:
            id_in_submission_data = data["flow"].get("id")
            flow_id = self.flow_id
            if not id_in_submission_data:
                data["flow"]["id"] = flow_id  # Make sure flow id is set
                msg = f"Flow ID is not set in submission data. Set it to {flow_id} from request."
                logging.warning(msg)
            elif id_in_submission_data != flow_id:
                data["flow"]["id"] = flow_id
                logging.warning(
                    "Flow ID %s in submission data does not match the one in request %s, update it.",
                    id_in_submission_data,
                    flow_id,
                )
        eval_flow_data = data.get("eval_flow")
        if eval_flow_data and not eval_flow_data.get("id"):
            raise MissingEvalFlowId(message_format="Evaluation flow is submitted but its ID is not set.")

        self.submission_data = SubmitFlowRequest._deserialize_submission_data(self.run_mode, data)

    @staticmethod
    def _deserialize_request(class_type: Type[T], data) -> T:
        try:
            return class_type.deserialize(data)
        except Exception as ex:
            raise FlowRequestDeserializeError(
                message_format="Failed to deserialize {class_name} due to {exception}.",
                class_name=class_type.__name__,
                exception=str(ex),
            ) from ex

    @staticmethod
    def _deserialize_submission_data(run_mode, data) -> Union[BatchFlowRequest, EvalRequest, NodesRequest]:
        if run_mode == RunMode.Flow or run_mode == RunMode.BulkTest:
            request = SubmitFlowRequest._deserialize_request(BatchFlowRequest, data)
        elif run_mode == RunMode.Eval:
            request = SubmitFlowRequest._deserialize_request(EvalRequest, data)
        elif run_mode == RunMode.SingleNode or run_mode == RunMode.FromNode:
            request = SubmitFlowRequest._deserialize_request(NodesRequest, data)
        else:
            raise InvalidRunMode(message_format="Invalid run_mode value: {run_mode}", run_mode=run_mode)
        return request

    @staticmethod
    def deserialize(data: dict) -> "SubmitFlowRequest":
        data = normalize_dict_keys_camel_to_snake(data)

        req = SubmitFlowRequest(
            flow_id=data.get("flow_id", ""),
            flow_run_id=data.get("flow_run_id", ""),
            source_flow_run_id=data.get("source_flow_run_id", ""),
            submission_data=data.get("submission_data", {}),
            flow_source=data.get("flow_source"),
            run_mode=RunMode(data.get("run_mode", 0)),
            created_by=CreatedBy.deserialize(data.get("created_by", {})),
            batch_data_input=BatchDataInput.deserialize(data.get("batch_data_input", {})),
            bulk_test_data_input=BatchDataInput.deserialize(data.get("bulk_test_data_input", {})),
            workspace_msi_token_for_storage_resource=data.get("workspace_msi_token_for_storage_resource", ""),
            environment_variables=data.get("environment_variables", {}),
            run_id_to_log_path=data.get("flow_run_logs", {}),
            app_insights_instrumentation_key=data.get("app_insights_instrumentation_key", ""),
            azure_storage_setting=AzureStorageSetting.deserialize(data.get("azure_storage_setting", {})),
        )

        if req.flow_source is not None:
            req.flow_source = FlowSource.deserialize(req.flow_source)
        # deserialize submission data to actual request type
        req._normalize_submission_data()

        return req

    @staticmethod
    def desensitize_to_json(req: "SubmitFlowRequest") -> str:
        """This function is used to desensitize request for logging."""
        ignored_keys = ["workspace_msi_token_for_storage_resource", "connections"]
        place_holder = "**data_scrubbed**"
        data = asdict(
            req, dict_factory=lambda x: {k: place_holder if k in ignored_keys else serialize(v) for (k, v) in x if v}
        )
        return json.dumps(data)

    def get_bulk_test_variants_run_ids(self):
        """Get all variants run ids for bulk test"""
        run_ids = []
        if isinstance(self.submission_data, BatchFlowRequest):
            if self.submission_data.variants_runs:
                run_ids = list(self.submission_data.variants_runs.values())
        return run_ids

    def get_root_run_ids(self):
        """Get all root run ids includes variant and evaluation runs except the shell(parent run)"""
        root_run_ids = [self.flow_run_id]
        if isinstance(self.submission_data, BatchFlowRequest):
            #  Variants
            root_run_ids += self.get_bulk_test_variants_run_ids()
            # Evaluation
            if self.submission_data.eval_flow and self.submission_data.eval_flow_run_id:
                root_run_ids.append(self.submission_data.eval_flow_run_id)
        return root_run_ids

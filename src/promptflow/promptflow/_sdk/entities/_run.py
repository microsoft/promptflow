# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import json
import uuid
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dateutil import parser as date_parser

from promptflow._sdk._constants import (
    BASE_PATH_CONTEXT_KEY,
    PARAMS_OVERRIDE_KEY,
    AzureRunTypes,
    FlowRunProperties,
    RestRunTypes,
    RunDataKeys,
    RunInfoSources,
    RunStatus,
    RunTypes,
    get_run_output_path,
)
from promptflow._sdk._errors import InvalidRunError, InvalidRunStatusError
from promptflow._sdk._orm import RunInfo as ORMRun
from promptflow._sdk._utils import _sanitize_python_variable_name, parse_variant
from promptflow._sdk.entities._yaml_translatable import YAMLTranslatableMixin
from promptflow._sdk.schemas._run import RunSchema
from promptflow.exceptions import UserErrorException

AZURE_RUN_TYPE_2_RUN_TYPE = {
    AzureRunTypes.BATCH: RunTypes.BATCH,
    AzureRunTypes.EVALUATION: RunTypes.EVALUATION,
    AzureRunTypes.PAIRWISE_EVALUATE: RunTypes.PAIRWISE_EVALUATE,
}

REST_RUN_TYPE_2_RUN_TYPE = {
    RestRunTypes.BATCH: RunTypes.BATCH,
    RestRunTypes.EVALUATION: RunTypes.EVALUATION,
    RestRunTypes.PAIRWISE_EVALUATE: RunTypes.PAIRWISE_EVALUATE,
}


class Run(YAMLTranslatableMixin):
    def __init__(
        self,
        flow: Path,
        name: str = None,
        # input fields are optional since it's not stored in DB
        data: str = None,
        variant: str = None,
        run: Union["Run", str] = None,
        column_mapping: dict = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        *,
        created_on: Optional[datetime.datetime] = None,
        start_time: Optional[datetime.datetime] = None,
        end_time: Optional[datetime.datetime] = None,
        status: Optional[str] = None,
        environment_variables: Dict[str, str] = None,
        connections: Dict[str, Dict] = None,
        properties: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Flow run.

        :param name: Name of the run.
        :type name: str
        :param type: Type of the run, should be one of "bulk", "evaluate" or "pairwise_evaluate".
        :type type: str
        :param flow: Path of the flow directory.
        :type flow: Path
        :param display_name: Display name of the run.
        :type display_name: str
        :param description: Description of the run.
        :type description: str
        :param tags: Tags of the run.
        :type tags: List[Dict[str, str]]
        """
        # TODO: remove when RUN CRUD don't depend on this
        self.type = RunTypes.BATCH
        self.data = data
        self.column_mapping = column_mapping
        self.display_name = display_name
        self.description = description
        self.tags = tags
        self.variant = variant
        self.run = run
        self._created_on = created_on or datetime.datetime.now()
        self._status = status or RunStatus.NOT_STARTED
        self.environment_variables = environment_variables or {}
        self.connections = connections or {}
        self._properties = properties or {}
        self._is_archived = kwargs.get("is_archived", False)
        self._run_source = kwargs.get("run_source", RunInfoSources.LOCAL)
        self._start_time = start_time
        self._end_time = end_time
        self._duration = kwargs.get("duration", None)
        self._portal_url = kwargs.get(RunDataKeys.PORTAL_URL, None)
        self._creation_context = kwargs.get("creation_context", None)
        if self._run_source == RunInfoSources.LOCAL:
            self.flow = Path(flow).resolve().absolute()
            self._flow_dir = self._get_flow_dir()
        elif self._run_source == RunInfoSources.INDEX_SERVICE:
            self._metrics = kwargs.get("metrics", {})
            self._experiment_name = kwargs.get("experiment_name", None)
        elif self._run_source == RunInfoSources.RUN_HISTORY:
            self._error = kwargs.get("error", None)
            self._data_portal_url = kwargs.get("data_portal_url", None)
            self._input_run_portal_url = kwargs.get("input_run_portal_url", None)
            self._output = kwargs.get("output", None)
            self._output_portal_url = kwargs.get("output_portal_url", None)
        self._runtime = kwargs.get("runtime", None)
        self._resources = kwargs.get("resources", None)
        # default run name: flow directory name + timestamp
        self.name = name or self._generate_run_name()
        # default to use name if display_name is not provided
        if not self.display_name:
            self.display_name = self.name

    @property
    def created_on(self) -> str:
        return self._created_on.isoformat()

    @property
    def status(self) -> str:
        return self._status

    @property
    def properties(self) -> Dict[str, str]:
        if self._run_source == RunInfoSources.LOCAL:
            # show posix path to avoid windows path escaping
            result = {
                FlowRunProperties.FLOW_PATH: Path(self.flow).as_posix(),
                FlowRunProperties.OUTPUT_PATH: Path(get_run_output_path(self)).as_posix(),
            }
            if self.run:
                run_name = self.run.name if isinstance(self.run, Run) else self.run
                result[FlowRunProperties.RUN] = run_name
            if self.variant:
                result[FlowRunProperties.NODE_VARIANT] = self.variant
            return {
                **result,
                **self._properties,
            }
        return self._properties

    @classmethod
    def _from_orm_object(cls, obj: ORMRun) -> "Run":
        properties_json = json.loads(str(obj.properties))
        return Run(
            name=str(obj.name),
            flow=Path(properties_json[FlowRunProperties.FLOW_PATH]),
            run=properties_json.get(FlowRunProperties.RUN, None),
            variant=properties_json.get(FlowRunProperties.NODE_VARIANT, None),
            display_name=obj.display_name,
            description=str(obj.description) if obj.description else None,
            tags=json.loads(str(obj.tags)) if obj.tags else None,
            # keyword arguments
            created_on=datetime.datetime.fromisoformat(str(obj.created_on)),
            start_time=datetime.datetime.fromisoformat(str(obj.start_time)) if obj.start_time else None,
            end_time=datetime.datetime.fromisoformat(str(obj.end_time)) if obj.end_time else None,
            status=str(obj.status),
            data=Path(obj.data).resolve().absolute().as_posix() if obj.data else None,
        )

    @classmethod
    def _from_index_service_entity(cls, run_entity: dict) -> "Run":
        """Convert run entity from index service to run object."""
        start_time = run_entity["properties"].get("startTime", None)
        end_time = run_entity["properties"].get("endTime", None)
        duration = run_entity["properties"].get("duration", None)
        return Run(
            name=run_entity["properties"]["runId"],
            flow=Path(f"azureml://flows/{run_entity['properties']['experimentName']}"),
            type=AZURE_RUN_TYPE_2_RUN_TYPE[run_entity["properties"]["runType"]],
            created_on=date_parser.parse(run_entity["properties"]["creationContext"]["createdTime"]),
            status=run_entity["annotations"]["status"],
            display_name=run_entity["annotations"]["displayName"],
            description=run_entity["annotations"]["description"],
            tags=run_entity["annotations"]["tags"],
            properties=run_entity["properties"]["userProperties"],
            is_archived=run_entity["annotations"]["archived"],
            run_source=RunInfoSources.INDEX_SERVICE,
            metrics=run_entity["annotations"]["metrics"],
            start_time=date_parser.parse(start_time) if start_time else None,
            end_time=date_parser.parse(end_time) if end_time else None,
            duration=duration,
            portal_url=run_entity[RunDataKeys.PORTAL_URL],
            creation_context=run_entity["properties"]["creationContext"],
            experiment_name=run_entity["properties"]["experimentName"],
        )

    @classmethod
    def _from_run_history_entity(cls, run_entity: dict) -> "Run":
        """Convert run entity from run history service to run object."""
        flow_name = run_entity["properties"].get("azureml.promptflow.flow_name", None)
        start_time = run_entity.get("startTimeUtc", None)
        end_time = run_entity.get("endTimeUtc", None)
        duration = run_entity.get("duration", None)
        return Run(
            name=run_entity["runId"],
            flow=Path(f"azureml://flows/{flow_name}"),
            type=AZURE_RUN_TYPE_2_RUN_TYPE[run_entity["runType"]],
            created_on=date_parser.parse(run_entity["createdUtc"]),
            start_time=date_parser.parse(start_time) if start_time else None,
            end_time=date_parser.parse(end_time) if end_time else None,
            duration=duration,
            status=run_entity["status"],
            display_name=run_entity["displayName"],
            description=run_entity["description"],
            tags=run_entity["tags"],
            properties=run_entity["properties"],
            is_archived=run_entity.get("archived", False),  # TODO: Get archived status, depends on run history team
            error=run_entity.get("error", None),
            run_source=RunInfoSources.RUN_HISTORY,
            portal_url=run_entity[RunDataKeys.PORTAL_URL],
            creation_context=run_entity["createdBy"],
            data=run_entity[RunDataKeys.DATA],
            data_portal_url=run_entity[RunDataKeys.DATA_PORTAL_URL],
            run=run_entity[RunDataKeys.RUN],
            input_run_portal_url=run_entity[RunDataKeys.INPUT_RUN_PORTAL_URL],
            output=run_entity[RunDataKeys.OUTPUT],
            output_portal_url=run_entity[RunDataKeys.OUTPUT_PORTAL_URL],
        )

    @classmethod
    def _from_mt_service_entity(cls, run_entity) -> "Run":
        """Convert run object from MT service to run object."""
        flow_run_id = run_entity.flow_run_resource_id.split("/")[-1]
        return cls(
            name=flow_run_id,
            flow=Path(f"azureml://flows/{run_entity.flow_name}"),
            display_name=run_entity.flow_run_display_name,
            description="",
            tags=[],
            created_on=date_parser.parse(run_entity.created_on),
            status="",
            run_source=RunInfoSources.MT_SERVICE,
        )

    def _to_orm_object(self) -> ORMRun:
        return ORMRun(
            name=self.name,
            created_on=self.created_on,
            status=self.status,
            start_time=self._start_time.isoformat() if self._start_time else None,
            end_time=self._end_time.isoformat() if self._end_time else None,
            display_name=self.display_name,
            description=self.description,
            tags=json.dumps(self.tags) if self.tags else None,
            properties=json.dumps(self.properties),
            data=Path(self.data).resolve().absolute().as_posix() if self.data else None,
        )

    def _dump(self) -> None:
        """Dump current run entity to local DB."""
        self._to_orm_object().dump()

    @property
    def _output_path(self) -> Path:
        return Path(self.properties[FlowRunProperties.OUTPUT_PATH])

    def _to_dict(self):
        from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations

        properties = self.properties
        result = {
            "name": self.name,
            "created_on": self.created_on,
            "status": self.status,
            "display_name": self.display_name,
            "description": self.description,
            "tags": self.tags,
            "properties": properties,
        }

        if self._run_source == RunInfoSources.LOCAL:
            result["flow_name"] = Path(str(self.flow)).resolve().name
            local_storage = LocalStorageOperations(run=self)
            result[RunDataKeys.DATA] = (
                local_storage._data_path.resolve().absolute().as_posix()
                if local_storage._data_path is not None
                else None
            )
            result[RunDataKeys.OUTPUT] = local_storage._outputs_path.as_posix()
            if self.run:
                run_name = self.run.name if isinstance(self.run, Run) else self.run
                result[RunDataKeys.RUN] = properties.pop(FlowRunProperties.RUN, run_name)
            # add exception part if any
            exception_dict = local_storage.load_exception()
            if exception_dict:
                result["error"] = exception_dict
        elif self._run_source == RunInfoSources.INDEX_SERVICE:
            result["creation_context"] = self._creation_context
            result["flow_name"] = self._experiment_name
            result["is_archived"] = self._is_archived
            result["start_time"] = self._start_time.isoformat() if self._start_time else None
            result["end_time"] = self._end_time.isoformat() if self._end_time else None
            result["duration"] = self._duration
        elif self._run_source == RunInfoSources.RUN_HISTORY:
            result["creation_context"] = self._creation_context
            result["start_time"] = self._start_time.isoformat() if self._start_time else None
            result["end_time"] = self._end_time.isoformat() if self._end_time else None
            result["duration"] = self._duration
            result[RunDataKeys.PORTAL_URL] = self._portal_url
            result[RunDataKeys.DATA] = self.data
            result[RunDataKeys.DATA_PORTAL_URL] = self._data_portal_url
            result[RunDataKeys.OUTPUT] = self._output
            result[RunDataKeys.OUTPUT_PORTAL_URL] = self._output_portal_url
            if self.run:
                result[RunDataKeys.RUN] = self.run
                result[RunDataKeys.INPUT_RUN_PORTAL_URL] = self._input_run_portal_url
            if self._error:
                result["error"] = self._error
        return result

    @classmethod
    def _load(
        cls,
        data: Optional[Dict] = None,
        yaml_path: Optional[Union[PathLike, str]] = None,
        params_override: Optional[list] = None,
        **kwargs,
    ):
        data = data or {}
        params_override = params_override or []
        context = {
            BASE_PATH_CONTEXT_KEY: Path(yaml_path).parent if yaml_path else Path("./"),
            PARAMS_OVERRIDE_KEY: params_override,
        }
        run = cls._load_from_dict(
            data=data,
            context=context,
            additional_message="Failed to load flow run",
            **kwargs,
        )
        if yaml_path:
            run._source_path = yaml_path
        return run

    def _generate_run_name(self) -> str:
        """Generate a run name with flow_name_variant_timestamp format."""
        try:
            flow_dir = self._get_flow_dir()
            variant = self.variant
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            variant = parse_variant(variant)[1] if variant else "default"
            run_name_prefix = f"{flow_dir}_{variant}"
            # TODO(2562996): limit run name to avoid it become too long
            run_name = f"{run_name_prefix}_{timestamp}"
            return _sanitize_python_variable_name(run_name)
        except Exception:
            return str(uuid.uuid4())

    def _get_flow_dir(self):
        flow = Path(self.flow)
        if flow.is_dir():
            return flow.name
        return self.flow.parent.name

    @classmethod
    def _get_schema_cls(self):
        return RunSchema

    def _to_rest_object(self):
        from azure.ai.ml._utils._storage_utils import AzureMLDatastorePathUri

        from promptflow.azure._restclient.flow.models import BatchDataInput, SubmitBulkRunRequest

        if self.run is not None:
            if isinstance(self.run, Run):
                variant = self.run.name
            elif isinstance(self.run, str):
                variant = self.run
            else:
                raise UserErrorException(f"Invalid run type: {type(self.run)}")
        else:
            variant = None

        if not variant and not self.data:
            raise UserErrorException("Either run or data should be provided")

        # sanitize flow_dir to avoid invalid experiment name
        run_experiment_name = _sanitize_python_variable_name(self._flow_dir)

        # parse inputs mapping
        inputs_mapping = {}
        if self.column_mapping and not isinstance(self.column_mapping, dict):
            raise UserErrorException(f"column_mapping should be a dictionary, got {type(self.column_mapping)} instead.")
        if self.column_mapping:
            for k, v in self.column_mapping.items():
                if isinstance(v, (int, float, str, bool)):
                    inputs_mapping[k] = v
                else:
                    try:
                        val = json.dumps(v)
                    except Exception as e:
                        raise UserErrorException(
                            f"Invalid input mapping value: {v}, "
                            f"only primitive or json serializable value is supported, got {type(v)}",
                            error=e,
                        )
                    inputs_mapping[k] = val

        if str(self.flow).startswith("azureml://"):
            # upload via _check_and_upload_path
            # submit with params FlowDefinitionDataStoreName and FlowDefinitionBlobPath
            path_uri = AzureMLDatastorePathUri(str(self.flow))
            return SubmitBulkRunRequest(
                flow_definition_data_store_name=path_uri.datastore,
                flow_definition_blob_path=path_uri.path,
                run_id=self.name,
                run_display_name=self.display_name,
                description=self.description,
                tags=self.tags,
                node_variant=self.variant,
                variant_run_id=variant,
                batch_data_input=BatchDataInput(
                    data_uri=self.data,
                ),
                inputs_mapping=inputs_mapping,
                run_experiment_name=run_experiment_name,
                environment_variables=self.environment_variables,
                connections=self.connections,
            )
        else:
            # upload via CodeOperations.create_or_update
            # submit with param FlowDefinitionDataUri
            return SubmitBulkRunRequest(
                flow_definition_data_uri=str(self.flow),
                run_id=self.name,
                run_display_name=self.display_name,
                description=self.description,
                tags=self.tags,
                node_variant=self.variant,
                variant_run_id=variant,
                batch_data_input=BatchDataInput(
                    data_uri=self.data,
                ),
                inputs_mapping=inputs_mapping,
                run_experiment_name=run_experiment_name,
                environment_variables=self.environment_variables,
                connections=self.connections,
            )

    def _check_run_status_is_completed(self) -> None:
        if self.status != RunStatus.COMPLETED:
            error_message = f"Run {self.name!r} is not completed, the status is {self.status!r}."
            if self.status != RunStatus.FAILED:
                error_message += " Please wait for its completion, or select other completed run(s)."
            raise InvalidRunStatusError(error_message)

    @staticmethod
    def _validate_and_return_run_name(run: Union[str, "Run"]) -> str:
        """Check if run name is valid."""
        if isinstance(run, Run):
            return run.name
        elif isinstance(run, str):
            return run
        raise InvalidRunError(f"Invalid run {run!r}, expected 'str' or 'Run' object but got {type(run)!r}.")

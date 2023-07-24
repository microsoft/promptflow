# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import datetime
import json
import time
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dateutil import parser as date_parser

from promptflow.sdk._constants import (
    BASE_PATH_CONTEXT_KEY,
    PARAMS_OVERRIDE_KEY,
    PORTAL_URL_KEY,
    AzureRunTypes,
    FlowRunProperties,
    RestRunTypes,
    RunInfoSources,
    RunStatus,
    RunTypes,
    get_run_output_path,
)
from promptflow.sdk._orm import RunInfo as ORMRun
from promptflow.sdk.entities._yaml_translatable import YAMLTranslatableMixin
from promptflow.sdk.schemas._run import RunSchema

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
        name: str,
        flow: Path,
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
        self.name = name
        # TODO: remove this when ORM supports no type
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
        self._portal_url = kwargs.get(PORTAL_URL_KEY, None)
        self._creation_context = kwargs.get("creation_context", None)
        if self._run_source == RunInfoSources.LOCAL:
            self.flow = Path(flow).resolve().absolute()
            self._flow_dir = self._get_flow_dir()
            # default run name: flow directory name + timestamp
            if not self.display_name:
                self.display_name = f"{self.flow.name}-{int(time.time())}"
        elif self._run_source == RunInfoSources.INDEX_SERVICE:
            self._metrics = kwargs.get("metrics", {})
            self._experiment_name = kwargs.get("experiment_name", None)
        elif self._run_source == RunInfoSources.RUN_HISTORY:
            self._error = kwargs.get("error", None)
        self._runtime = kwargs.get("runtime", None)
        self._resources = kwargs.get("resources", {})

    @property
    def created_on(self) -> str:
        return self._created_on.isoformat()

    @property
    def status(self) -> str:
        return self._status

    @property
    def properties(self) -> Dict[str, str]:
        if self._run_source == RunInfoSources.LOCAL:
            result = {
                FlowRunProperties.FLOW_PATH: str(self.flow),
                FlowRunProperties.OUTPUT_PATH: str(get_run_output_path(self)),
            }
            if self.run:
                run_name = self.run.name if isinstance(self.run, Run) else self.run
                result[FlowRunProperties.RUN] = run_name
            if self.variant:
                result[FlowRunProperties.NODE_VARIANT] = self.variant
            return result
        return self._properties

    @classmethod
    def _from_orm_object(cls, obj: ORMRun) -> "Run":
        properties_json = json.loads(str(obj.properties))
        return Run(
            name=str(obj.name),
            flow=Path(properties_json[FlowRunProperties.FLOW_PATH]),
            run=properties_json.get(FlowRunProperties.RUN, None),
            variant=properties_json.get(FlowRunProperties.NODE_VARIANT, None),
            display_name=str(obj.display_name),
            description=str(obj.description) if obj.description else None,
            tags=json.loads(str(obj.tags)) if obj.tags else None,
            # keyword arguments
            created_on=datetime.datetime.fromisoformat(str(obj.created_on)),
            start_time=datetime.datetime.fromisoformat(str(obj.start_time)) if obj.start_time else None,
            end_time=datetime.datetime.fromisoformat(str(obj.end_time)) if obj.end_time else None,
            status=str(obj.status),
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
            portal_url=run_entity[PORTAL_URL_KEY],
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
            portal_url=run_entity[PORTAL_URL_KEY],
            creation_context=run_entity["createdBy"],
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
            type=self.type,
            created_on=self.created_on,
            status=self.status,
            start_time=self._start_time.isoformat() if self._start_time else None,
            end_time=self._end_time.isoformat() if self._end_time else None,
            display_name=self.display_name,
            description=self.description,
            tags=json.dumps(self.tags) if self.tags else None,
            properties=json.dumps(self.properties),
        )

    def _dump(self) -> None:
        """Dump current run entity to local DB."""
        self._to_orm_object().dump()

    @property
    def _output_path(self) -> Path:
        return Path(self.properties[FlowRunProperties.OUTPUT_PATH])

    def _to_dict(self):
        result = {
            "name": self.name,
            "created_on": self.created_on,
            "status": self.status,
            "display_name": self.display_name,
            "description": self.description,
            "tags": self.tags,
            "properties": self.properties,
        }

        if self._run_source == RunInfoSources.LOCAL:
            result["flow_name"] = str(self.flow)
            result["output_path"] = str(self._output_path)
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
            result[PORTAL_URL_KEY] = self._portal_url
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

    def _get_flow_dir(self):
        flow = Path(self.flow)
        if flow.is_dir():
            return flow.name
        return self.flow.parent.name

    @classmethod
    def _get_schema_cls(self):
        return RunSchema

    def _to_rest_object(self):
        from promptflow.azure._restclient.flow.models import BatchDataInput, SubmitBulkRunRequest

        if self.run is not None:
            if isinstance(self.run, Run):
                variant = self.run.name
            elif isinstance(self.run, str):
                variant = self.run
            else:
                raise ValueError(f"Invalid run type: {type(self.run)}")
        else:
            variant = None

        if not variant and not self.data:
            raise ValueError("Either run or data should be provided")

        return SubmitBulkRunRequest(
            flow_definition_file_path=self.flow,
            run_id=self.name,
            run_display_name=self.display_name,
            description=self.description,
            tags=self.tags,
            node_variant=self.variant,
            variant_run_id=variant,
            batch_data_input=BatchDataInput(
                data_uri=self.data,
            ),
            inputs_mapping=self.column_mapping,
            run_experiment_name=self._flow_dir,
            environment_variables=self.environment_variables,
        )

# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import dataclasses
import datetime
import functools
import json
import uuid
from dataclasses import asdict
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dateutil import parser as date_parser

from promptflow._constants import OutputsFolderName, TokenKeys
from promptflow._sdk._configuration import Configuration
from promptflow._sdk._constants import (
    BASE_PATH_CONTEXT_KEY,
    DEFAULT_ENCODING,
    DEFAULT_VARIANT,
    FLOW_DIRECTORY_MACRO_IN_CONFIG,
    FLOW_RESOURCE_ID_PREFIX,
    HOME_PROMPT_FLOW_DIR,
    PARAMS_OVERRIDE_KEY,
    PF_SYSTEM_METRICS_PREFIX,
    REGISTRY_URI_PREFIX,
    REMOTE_URI_PREFIX,
    RUN_MACRO,
    TIMESTAMP_MACRO,
    VARIANT_ID_MACRO,
    AzureRunTypes,
    CloudDatastore,
    DownloadedRun,
    FlowRunProperties,
    IdentityKeys,
    Local2CloudProperties,
    Local2CloudUserProperties,
    LocalStorageFilenames,
    RestRunTypes,
    RunDataKeys,
    RunInfoSources,
    RunStatus,
    RunTypes,
)
from promptflow._sdk._errors import InvalidRunError, InvalidRunStatusError, MissingAzurePackage
from promptflow._sdk._orm import RunInfo as ORMRun
from promptflow._sdk._utilities.general_utils import (
    _sanitize_python_variable_name,
    is_multi_container_enabled,
    is_remote_uri,
    parse_remote_flow_pattern,
)
from promptflow._sdk.entities._yaml_translatable import YAMLTranslatableMixin
from promptflow._sdk.schemas._run import RunSchema
from promptflow._utils.flow_utils import (
    get_flow_lineage_id,
    get_flow_type,
    is_flex_flow,
    is_prompty_flow,
    parse_variant,
)
from promptflow._utils.logger_utils import get_cli_sdk_logger
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


logger = get_cli_sdk_logger()


class Run(YAMLTranslatableMixin):
    """Flow run entity.

    :param flow: Path of local flow entry or remote flow.
    :type flow: Path
    :param name: Name of the run.
    :type name: str
    :param data: Input data for the run. Local path or remote uri(starts with azureml: or public URL) are supported. Note: remote uri is only supported for cloud run. # noqa: E501
    :type data: Optional[str]
    :param variant: Variant of the run.
    :type variant: Optional[str]
    :param run: Parent run or run ID.
    :type run: Optional[Union[Run, str]]
    :param column_mapping: Column mapping for the run. Optional since it's not stored in the database.
    :type column_mapping: Optional[dict]
    :param display_name: Display name of the run.
    :type display_name: Optional[str]
    :param description: Description of the run.
    :type description: Optional[str]
    :param tags: Tags of the run.
    :type tags: Optional[List[Dict[str, str]]]
    :param created_on: Date and time the run was created.
    :type created_on: Optional[datetime.datetime]
    :param start_time: Date and time the run started.
    :type start_time: Optional[datetime.datetime]
    :param end_time: Date and time the run ended.
    :type end_time: Optional[datetime.datetime]
    :param status: Status of the run.
    :type status: Optional[str]
    :param environment_variables: Environment variables for the run.
    :type environment_variables: Optional[Dict[str, str]]
    :param connections: Connections for the run.
    :type connections: Optional[Dict[str, Dict]]
    :param properties: Properties of the run.
    :type properties: Optional[Dict[str, Any]]
    :param init: Class init arguments for callable class, only supported for flex flow.
    :type init: Optional[Dict[str, Any]]
    :param kwargs: Additional keyword arguments.
    :type kwargs: Optional[dict]
    """

    def __init__(
        self,
        flow: Optional[Union[Path, str]] = None,
        name: Optional[str] = None,
        # input fields are optional since it's not stored in DB
        data: Optional[str] = None,
        variant: Optional[str] = None,
        run: Optional[Union["Run", str]] = None,
        column_mapping: Optional[dict] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        *,
        created_on: Optional[datetime.datetime] = None,
        start_time: Optional[datetime.datetime] = None,
        end_time: Optional[datetime.datetime] = None,
        status: Optional[str] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        connections: Optional[Dict[str, Dict]] = None,
        properties: Optional[Dict[str, Any]] = None,
        source: Optional[Union[Path, str]] = None,
        init: Optional[Dict[str, Any]] = None,
        # !!! Caution !!!: Please update self._copy() if you add new fields to init
        # TODO: remove when RUN CRUD don't depend on this
        **kwargs,
    ):
        self.type = kwargs.get("type", RunTypes.BATCH)
        self.data = data
        self.column_mapping = column_mapping
        self.display_name = display_name
        self.description = description
        self.tags = tags
        self.variant = variant
        self.run = run
        self._resume_from = kwargs.get("resume_from", None)
        self._created_on = created_on or datetime.datetime.now().astimezone()
        self._status = status or RunStatus.NOT_STARTED
        self.environment_variables = environment_variables or {}
        self.connections = connections or {}
        self._properties = properties or {}
        self.source = source
        self._is_archived = kwargs.get("is_archived", False)
        self._run_source = kwargs.get("run_source", RunInfoSources.LOCAL)
        self._start_time = start_time
        self._end_time = end_time
        self._duration = kwargs.get("duration", None)
        self._portal_url = kwargs.get(RunDataKeys.PORTAL_URL, None)
        self._creation_context = kwargs.get("creation_context", None)
        # init here to make sure those fields initialized in all branches.
        self.flow = flow
        self._use_remote_flow = is_remote_uri(flow)
        self._experiment_name = None
        self._lineage_id = None
        if self._use_remote_flow:
            self._flow_name = parse_remote_flow_pattern(flow)
            self._lineage_id = self._flow_name
        # record if run is from flex flow or prompty if possible, there's no variant in run name for flex flow
        if self._run_source == RunInfoSources.LOCAL:
            try:
                self._from_flex_flow = is_flex_flow(flow_path=self.flow)
            except Exception:
                self._from_flex_flow = False
            try:
                self._from_prompty = is_prompty_flow(self.flow)
            except Exception:
                self._from_prompty = False
        else:
            self._from_flex_flow = False
            self._from_prompty = False
        # default run name: flow directory name + timestamp
        self.name = name or self._generate_run_name()
        experiment_name = kwargs.get("experiment_name", None)
        self._config: Configuration = kwargs.get("config", Configuration.get_instance())
        if self._run_source == RunInfoSources.LOCAL and not self._use_remote_flow:
            self.flow = Path(str(flow)).resolve().absolute()
            flow_dir = self._get_flow_dir()
            # sanitize flow_dir to avoid invalid experiment name
            self._experiment_name = _sanitize_python_variable_name(flow_dir.name)
            self._lineage_id = get_flow_lineage_id(flow_dir=flow_dir)
            self._output_path = Path(kwargs.get("output_path", self._generate_output_path(config=self._config)))
            if self._from_prompty:
                self._flow_name = Path(self.flow).stem
            else:
                self._flow_name = flow_dir.name
        elif self._run_source == RunInfoSources.INDEX_SERVICE:
            self._metrics = kwargs.get("metrics", {})
            self._experiment_name = experiment_name
        elif self._run_source == RunInfoSources.RUN_HISTORY:
            self._error = kwargs.get("error", None)
            self._output = kwargs.get("output", None)
        elif self._run_source == RunInfoSources.EXISTING_RUN:
            # when the run is created from an existing run folder, the output path is also the source path
            self._output_path = Path(source)
        self._runtime = kwargs.get("runtime", None)
        self._resources = kwargs.get("resources", None)
        self._identity = kwargs.get("identity", {})
        self._outputs = kwargs.get("outputs", None)
        self._command = kwargs.get("command", None)
        # To support `pf.run` for dynamic callable, we need to create a run whose target function is a dynamic callable.
        # TODO: such run is not resumable, not sure if we need specific error message for this case.
        self._dynamic_callable = kwargs.get("dynamic_callable", None)
        if init:
            # validate if provided init kwargs for early exception
            self._validate_init(init)
            self._properties[FlowRunProperties.INIT_KWARGS] = init

    def _copy(self, **kwargs):
        """Copy a new run object.

        This is used for resume run scenario, a new run will be created with the same properties as the original run.
        Allowed to override some properties with kwargs. Supported properties are:
        Meta: name, display_name, description, tags.
        Run setting: runtime, resources, identity.
        """
        init_properties = {"init_kwargs": self.properties["init_kwargs"]} if "init_kwargs" in self.properties else {}
        init_params = {
            "flow": self.flow,
            "data": self.data,
            "variant": self.variant,
            "run": self.run,
            "column_mapping": self.column_mapping,
            "display_name": self.display_name,
            "description": self.description,
            "tags": self.tags,
            "environment_variables": self.environment_variables,
            "connections": self.connections,
            "properties": init_properties,  # copy no properties except init_kwargs
            "source": self.source,
            "identity": self._identity,
            **kwargs,
        }
        logger.debug(f"Run init params: {init_params}")
        return Run(**init_params)

    @property
    def created_on(self) -> str:
        return self._created_on.isoformat()

    @property
    def status(self) -> str:
        return self._status

    @property
    def properties(self) -> Dict[str, str]:
        result = {}
        if self._run_source == RunInfoSources.LOCAL:
            # show posix path to avoid windows path escaping
            result = {
                FlowRunProperties.FLOW_PATH: Path(self.flow).as_posix() if not self._use_remote_flow else self.flow,
                FlowRunProperties.OUTPUT_PATH: self._output_path.as_posix(),
            }
            if self.run:
                run_name = self.run.name if isinstance(self.run, Run) else self.run
                result[FlowRunProperties.RUN] = run_name
            if self.variant:
                result[FlowRunProperties.NODE_VARIANT] = self.variant
            if self._command:
                result[FlowRunProperties.COMMAND] = self._command
            if self._outputs:
                result[FlowRunProperties.OUTPUTS] = self._outputs
            if self._resume_from:
                resume_from_name = self._resume_from.name if isinstance(self._resume_from, Run) else self._resume_from
                result[FlowRunProperties.RESUME_FROM] = resume_from_name
            if self.column_mapping:
                result[FlowRunProperties.COLUMN_MAPPING] = self.column_mapping
        elif self._run_source == RunInfoSources.EXISTING_RUN:
            result = {
                FlowRunProperties.OUTPUT_PATH: Path(self.source).resolve().as_posix(),
            }

        return {
            **result,
            **self._properties,
        }

    @property
    def init(self):
        return self._properties.get(FlowRunProperties.INIT_KWARGS, None)

    @classmethod
    def _from_orm_object(cls, obj: ORMRun) -> "Run":
        properties_json = json.loads(str(obj.properties))
        flow = properties_json.get(FlowRunProperties.FLOW_PATH, None)

        # there can be two sources for orm run object:
        # 1. LOCAL: Created when run is created from local flow
        # 2. EXISTING_RUN: Created when run is created from existing run folder
        source = None
        if getattr(obj, "run_source", None) == RunInfoSources.EXISTING_RUN:
            source = properties_json[FlowRunProperties.OUTPUT_PATH]

        return Run(
            type=obj.type,
            name=str(obj.name),
            flow=Path(flow) if flow else None,
            source=Path(source) if source else None,
            output_path=properties_json[FlowRunProperties.OUTPUT_PATH],
            run=properties_json.get(FlowRunProperties.RUN, None),
            variant=properties_json.get(FlowRunProperties.NODE_VARIANT, None),
            resume_from=properties_json.get(FlowRunProperties.RESUME_FROM, None),
            display_name=obj.display_name,
            description=str(obj.description) if obj.description else None,
            tags=json.loads(str(obj.tags)) if obj.tags else None,
            # keyword arguments
            created_on=datetime.datetime.fromisoformat(str(obj.created_on)),
            start_time=datetime.datetime.fromisoformat(str(obj.start_time)) if obj.start_time else None,
            end_time=datetime.datetime.fromisoformat(str(obj.end_time)) if obj.end_time else None,
            status=str(obj.status),
            data=Path(obj.data).resolve().absolute().as_posix() if obj.data else None,
            properties=properties_json,
            # compatible with old runs, their run_source is empty, treat them as local
            run_source=obj.run_source or RunInfoSources.LOCAL,
            # experiment command node only fields
            command=properties_json.get(FlowRunProperties.COMMAND, None),
            outputs=properties_json.get(FlowRunProperties.OUTPUTS, None),
            column_mapping=properties_json.get(FlowRunProperties.COLUMN_MAPPING, None),
            portal_url=obj.portal_url,
        )

    @classmethod
    def _from_index_service_entity(cls, run_entity: dict) -> "Run":
        """Convert run entity from index service to run object."""
        # TODO(2887134): support cloud eager Run CRUD
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
            creation_context=run_entity["properties"]["creationContext"],
            experiment_name=run_entity["properties"]["experimentName"],
        )

    @classmethod
    def _from_run_history_entity(cls, run_entity: dict) -> "Run":
        """Convert run entity from run history service to run object."""
        # TODO(2887134): support cloud eager Run CRUD
        flow_name = run_entity["properties"].get("azureml.promptflow.flow_name", None)
        start_time = run_entity.get("startTimeUtc", None)
        end_time = run_entity.get("endTimeUtc", None)
        duration = run_entity.get("duration", None)
        resume_from = run_entity["properties"].get("azureml.promptflow.resume_from_run_id", None)
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
            resume_from=resume_from,
            portal_url=run_entity[RunDataKeys.PORTAL_URL],
            creation_context=run_entity["createdBy"],
            data=run_entity[RunDataKeys.DATA],
            run=run_entity[RunDataKeys.RUN],
            output=run_entity[RunDataKeys.OUTPUT],
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
        """Convert current run entity to ORM object."""
        display_name = self._format_display_name()
        return ORMRun(
            type=self.type,
            name=self.name,
            created_on=self.created_on,
            status=self.status,
            start_time=self._start_time.isoformat() if self._start_time else None,
            end_time=self._end_time.isoformat() if self._end_time else None,
            display_name=display_name,
            description=self.description,
            tags=json.dumps(self.tags) if self.tags else None,
            properties=json.dumps(self.properties, default=asdict),
            data=Path(self.data).resolve().absolute().as_posix() if self.data else None,
            run_source=self._run_source,
            portal_url=self._portal_url,
        )

    def _dump(self) -> None:
        """Dump current run entity to local DB."""
        self._to_orm_object().dump()

    def _to_dict(
        self,
        *,
        exclude_additional_info: bool = False,
        exclude_debug_info: bool = False,
        exclude_properties: bool = False,
    ):
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
            result["flow_name"] = self._flow_name
            local_storage = LocalStorageOperations(run=self)
            result[RunDataKeys.DATA] = (
                local_storage._data_path.resolve().absolute().as_posix()
                if local_storage._data_path is not None
                else None
            )
            result[RunDataKeys.OUTPUT] = local_storage.outputs_folder.as_posix()
            if self.run:
                run_name = self.run.name if isinstance(self.run, Run) else self.run
                result[RunDataKeys.RUN] = properties.pop(FlowRunProperties.RUN, run_name)
            # add exception part if any
            exception_dict = local_storage.load_exception()
            if exception_dict:
                if exclude_additional_info:
                    exception_dict.pop("additionalInfo", None)
                if exclude_debug_info:
                    exception_dict.pop("debugInfo", None)
                result["error"] = exception_dict
            if self._portal_url:
                result[RunDataKeys.PORTAL_URL] = self._portal_url
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
            result[RunDataKeys.OUTPUT] = self._output
            if self.run:
                result[RunDataKeys.RUN] = self.run
            if self._error:
                result["error"] = self._error
                if exclude_additional_info:
                    result["error"]["error"].pop("additionalInfo", None)
                if exclude_debug_info:
                    result["error"]["error"].pop("debugInfo", None)

        # hide system metrics that starts with '__pf__'
        system_metrics = properties.get(FlowRunProperties.SYSTEM_METRICS, None)
        if system_metrics and isinstance(system_metrics, dict):
            refined_system_metrics = {
                k: v for k, v in system_metrics.items() if not k.startswith(PF_SYSTEM_METRICS_PREFIX)
            }
            properties[FlowRunProperties.SYSTEM_METRICS] = refined_system_metrics

        # hide properties when needed (e.g. list remote runs)
        if exclude_properties is True:
            result.pop("properties", None)

        return result

    @classmethod
    def _load(
        cls,
        data: Optional[Dict] = None,
        yaml_path: Optional[Union[PathLike, str]] = None,
        params_override: Optional[list] = None,
        **kwargs,
    ):
        from marshmallow import INCLUDE

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
            unknown=INCLUDE,
            **kwargs,
        )
        if yaml_path:
            run._source_path = yaml_path
        return run

    def _generate_run_name(self) -> str:
        """Generate a run name with flow_name_variant_timestamp format."""
        try:
            flow_name = self._get_flow_dir().name if not self._use_remote_flow else self._flow_name
            variant = self.variant
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            if not self._from_prompty and not self._from_flex_flow:
                variant = parse_variant(variant)[1] if variant else DEFAULT_VARIANT
                run_name_prefix = f"{flow_name}_{variant}"
            else:
                run_name_prefix = flow_name
            # TODO(2562996): limit run name to avoid it become too long
            run_name = f"{run_name_prefix}_{timestamp}"
            return _sanitize_python_variable_name(run_name)
        except Exception:
            return str(uuid.uuid4())

    def _get_default_display_name(self) -> str:
        display_name = self.display_name or self.name
        return display_name

    def _format_display_name(self) -> str:
        """
        Format display name. Replace macros in display name with actual values.
        The following macros are supported: ${variant_id}, ${run}, ${timestamp}

        For example,
            if the display name is "run-${variant_id}-${timestamp}"
            it will be formatted to "run-variant_1-20210901123456"
        """
        display_name = self._get_default_display_name()
        time_stamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        if self.run:
            display_name = display_name.replace(RUN_MACRO, self._validate_and_return_run_name(self.run))
        display_name = display_name.replace(TIMESTAMP_MACRO, time_stamp)

        if not self._from_flex_flow and not self._from_prompty:
            variant = self.variant
            variant = parse_variant(variant)[1] if variant else DEFAULT_VARIANT
            display_name = display_name.replace(VARIANT_ID_MACRO, variant)

        return display_name

    def _get_flow_dir(self) -> Path:
        if not self._use_remote_flow:
            flow = Path(str(self.flow)).resolve().absolute()
            if flow.is_dir():
                return flow
            return flow.parent
        raise UserErrorException("Cannot get flow directory for remote flow.")

    @classmethod
    def _get_schema_cls(self):
        return RunSchema

    @classmethod
    def _validate_init(cls, init: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and parse init kwargs."""
        if not init:
            return {}
        if not isinstance(init, dict):
            raise UserErrorException(f"Invalid init kwargs: {init}. Expecting a dictionary.")

        try:
            json.dumps(init, default=asdict)
        except Exception as e:
            raise UserErrorException(f"Invalid init kwargs: {init}. Expecting a json serializable dictionary.") from e

    @classmethod
    def _to_rest_init(cls, init):
        """Convert init to rest object."""
        if not init:
            return None
        return {k: asdict(v) if dataclasses.is_dataclass(v) else v for k, v in init.items()}

    def _to_rest_object(self):
        try:
            from azure.ai.ml._utils._storage_utils import AzureMLDatastorePathUri

            from promptflow.azure._restclient.flow.models import (
                BatchDataInput,
                RunDisplayNameGenerationType,
                SessionSetupModeEnum,
                SubmitBulkRunRequest,
            )
        except ImportError:
            raise MissingAzurePackage()

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

        # parse resources
        if self._resources is not None:
            if not isinstance(self._resources, dict):
                raise TypeError(f"resources should be a dict, got {type(self._resources)} for {self._resources}")
            vm_size = self._resources.get("instance_type", None)
            compute_name = self._resources.get("compute", None)
        else:
            vm_size = None
            compute_name = None

        # parse identity resource id
        identity_resource_id = self._identity.get(IdentityKeys.RESOURCE_ID, None)

        # use functools.partial to avoid too many arguments that have the same values
        common_submit_bulk_run_request = functools.partial(
            SubmitBulkRunRequest,
            run_id=self.name,
            # will use user provided display name since PFS will have special logic to update it.
            run_display_name=self._get_default_display_name(),
            description=self.description,
            tags=self.tags,
            node_variant=self.variant,
            variant_run_id=variant,
            batch_data_input=BatchDataInput(
                data_uri=self.data,
            ),
            inputs_mapping=inputs_mapping,
            run_experiment_name=self._experiment_name,
            environment_variables=self.environment_variables,
            connections=self.connections,
            flow_lineage_id=self._lineage_id,
            run_display_name_generation_type=RunDisplayNameGenerationType.USER_PROVIDED_MACRO,
            vm_size=vm_size,
            session_setup_mode=SessionSetupModeEnum.SYSTEM_WAIT,
            compute_name=compute_name,
            identity=identity_resource_id,
            enable_multi_container=is_multi_container_enabled(),
            init_k_wargs=self._to_rest_init(self.init),
        )

        # use when uploading a local existing run to cloud
        local_to_cloud_info = getattr(self, "_local_to_cloud_info", None)

        if str(self.flow).startswith(REMOTE_URI_PREFIX):
            if not self._use_remote_flow:
                # in normal case, we will upload local flow to datastore and resolve the self.flow to be remote uri
                # upload via _check_and_upload_path
                # submit with params FlowDefinitionDataStoreName and FlowDefinitionBlobPath
                path_uri = AzureMLDatastorePathUri(str(self.flow))
                return common_submit_bulk_run_request(
                    flow_definition_data_store_name=path_uri.datastore,
                    flow_definition_blob_path=path_uri.path,
                )
            else:
                # if the flow is a remote flow in the beginning, we will submit with params FlowDefinitionResourceID
                # submit with params flow_definition_resource_id which will be resolved in pfazure run create operation
                # the flow resource id looks like: "azureml://locations/<region>/workspaces/<ws-name>/flows/<flow-name>"
                if not isinstance(self.flow, str) or (
                    not self.flow.startswith(FLOW_RESOURCE_ID_PREFIX) and not self.flow.startswith(REGISTRY_URI_PREFIX)
                ):
                    raise UserErrorException(
                        f"Invalid flow value when transforming to rest object: {self.flow!r}. "
                        f"Expecting a flow definition resource id starts with '{FLOW_RESOURCE_ID_PREFIX}' "
                        f"or a flow registry uri starts with '{REGISTRY_URI_PREFIX}'"
                    )
                return common_submit_bulk_run_request(
                    flow_definition_resource_id=self.flow,
                )
        elif local_to_cloud_info:
            # register local run to cloud
            return self._to_rest_object_for_local_to_cloud(local_to_cloud_info, variant)
        else:
            # upload via CodeOperations.create_or_update
            # submit with param FlowDefinitionDataUri
            return common_submit_bulk_run_request(
                flow_definition_data_uri=str(self.flow),
            )

    def _to_rest_object_for_local_to_cloud(self, local_to_cloud_info: dict, variant_run_id=None):
        """Convert run object to CreateExistingBulkRunRequest object for local to cloud operation."""
        from promptflow.azure._restclient.flow.models import CreateExistingBulkRunRequest, RunDisplayNameGenerationType

        # parse local_to_cloud_info to get necessary information
        flow_artifact_path = local_to_cloud_info[OutputsFolderName.FLOW_ARTIFACTS]
        flow_artifact_root_path = Path(flow_artifact_path).parent.as_posix()
        log_file_relative_path = local_to_cloud_info[LocalStorageFilenames.LOG]
        snapshot_file_path = local_to_cloud_info[LocalStorageFilenames.SNAPSHOT_FOLDER]

        # get the start and end time. Plus "Z" to specify the timezone is UTC, otherwise there will be warning
        # when sending the request to the server.
        # e.g. WARNING:msrest.serialization:Datetime with no tzinfo will be considered UTC.
        # for start_time, switch to "_start_time" once the bug item is fixed: BUG - 3085432.
        start_time = self._created_on.isoformat() if self._created_on else None
        end_time = self._end_time.isoformat() if self._end_time else None

        # extract properties that needs to be passed to the request
        properties = {
            # add instance_results.jsonl path to run properties, which is required by UI feature.
            Local2CloudProperties.EVAL_ARTIFACTS: '[{"path": "instance_results.jsonl", "type": "table"}]',
        }
        # add system metrics to run properties
        for token_key in TokenKeys.get_all_values():
            final_key = f"{Local2CloudProperties.PREFIX}.{token_key}"
            value = self.properties[FlowRunProperties.SYSTEM_METRICS].get(token_key, 0)
            if value is not None:
                properties[final_key] = value

        # add user properties to run properties
        for property_key in Local2CloudUserProperties.get_all_values():
            value = self.properties.get(property_key, None)
            if value is not None:
                properties[property_key] = value

        return CreateExistingBulkRunRequest(
            run_id=self.name,
            run_status=self.status,
            start_time_utc=start_time,
            end_time_utc=end_time,
            run_display_name=self._get_default_display_name(),
            description=self.description,
            tags=self.tags,
            variant_run_id=variant_run_id,
            properties=properties,
            run_experiment_name=self._experiment_name,
            run_display_name_generation_type=RunDisplayNameGenerationType.USER_PROVIDED_MACRO,
            output_data_store=CloudDatastore.DEFAULT,
            flow_artifacts_root_path=flow_artifact_root_path,
            log_file_relative_path=log_file_relative_path,
            flow_definition_data_store_name=CloudDatastore.DEFAULT,
            flow_definition_blob_path=snapshot_file_path,
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

    def _validate_for_run_create_operation(self):
        """Validate run object for create operation."""
        # check flow value
        if Path(self.flow).is_dir() or Path(self.flow).is_file():
            # local flow
            pass
        elif isinstance(self.flow, str) and self.flow.startswith(REMOTE_URI_PREFIX):
            # remote flow
            pass
        else:
            raise UserErrorException(
                f"Invalid flow value: {self.flow!r}. Expecting a local flow folder path or a remote flow pattern "
                f"like '{REMOTE_URI_PREFIX}<flow-name>'"
            )

        if is_remote_uri(self.data):
            # Pass through ARM id or remote url, the error will happen in runtime if format is not correct currently.
            pass
        else:
            if self.data and not Path(self.data).exists():
                raise UserErrorException(f"data path {self.data} does not exist")
        if not self.run and not self.data:
            raise UserErrorException("at least one of data or run must be provided")

    def _generate_output_path(self, config: Configuration) -> Path:
        path = config.get_run_output_path()
        if path is None:
            path = HOME_PROMPT_FLOW_DIR / ".runs"
        else:
            try:
                flow_posix_path = self.flow.resolve().as_posix()
                path = Path(path.replace(FLOW_DIRECTORY_MACRO_IN_CONFIG, self.flow.resolve().as_posix())).resolve()
                # in case user manually modifies ~/.promptflow/pf.yaml
                # fall back to default run output path
                if path.as_posix() == flow_posix_path:
                    raise Exception(f"{FLOW_DIRECTORY_MACRO_IN_CONFIG!r} is not a valid value.")
                path.mkdir(parents=True, exist_ok=True)
            except Exception:  # pylint: disable=broad-except
                path = HOME_PROMPT_FLOW_DIR / ".runs"
                warning_message = (
                    "Got unexpected error when parsing specified output path: "
                    f"{config.get_run_output_path()!r}; "
                    f"will use default output path: {path!r} instead."
                )
                logger.warning(warning_message)
        return (path / str(self.name)).resolve()

    @classmethod
    def _load_from_source(cls, source: Union[str, Path], params_override: Optional[Dict] = None, **kwargs) -> "Run":
        """Load run from run record source folder."""
        source = Path(source)
        params_override = params_override or {}

        run_metadata_file = source / DownloadedRun.RUN_METADATA_FILE_NAME
        if not run_metadata_file.exists():
            raise UserErrorException(
                f"Invalid run source: {source!r}. Expecting a valid run source folder with {run_metadata_file!r}. "
                f"Please make sure the run source is downloaded by 'pfazure run download' command."
            )
        # extract run info from source folder
        with open(source / DownloadedRun.RUN_METADATA_FILE_NAME, encoding=DEFAULT_ENCODING) as f:
            run_info = json.load(f)

        return cls(
            name=run_info["name"],
            source=source,
            run_source=RunInfoSources.EXISTING_RUN,
            status=run_info["status"],  # currently only support completed run
            display_name=params_override.get("display_name", run_info.get("display_name", source.name)),
            description=params_override.get("description", run_info.get("description", "")),
            tags=params_override.get("tags", run_info.get("tags", {})),
            created_on=datetime.datetime.fromisoformat(run_info["created_on"]),
            start_time=datetime.datetime.fromisoformat(run_info["start_time"]),
            end_time=datetime.datetime.fromisoformat(run_info["end_time"]),
            **kwargs,
        )

    @functools.cached_property
    def _flow_type(self) -> str:
        """Get flow type of run."""

        return get_flow_type(self.flow)

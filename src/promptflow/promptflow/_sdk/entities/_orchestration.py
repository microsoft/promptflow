# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY, PARAMS_OVERRIDE_KEY, JobType
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._yaml_translatable import YAMLTranslatableMixin
from promptflow._sdk.schemas._orchestration import AggregationJobSchema, FlowJobSchema, OrchestrationSchema


class FlowJob(YAMLTranslatableMixin):
    def __init__(
        self,
        flow: Union[Path, str],
        name: str,
        # input fields are optional since it's not stored in DB
        data: Optional[str] = None,
        variant: Optional[str] = None,
        run: Optional[Union["Run", str]] = None,
        column_mapping: Optional[dict] = None,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[Dict[str, str]]] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        connections: Optional[Dict[str, Dict]] = None,
        properties: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        self.type = JobType.FLOW
        self.data = data
        self.column_mapping = column_mapping
        self.display_name = display_name
        self.description = description
        self.tags = tags
        self.variant = variant
        self.run = run
        self.environment_variables = environment_variables or {}
        self.connections = connections or {}
        self._properties = properties or {}
        self._creation_context = kwargs.get("creation_context", None)
        # init here to make sure those fields initialized in all branches.
        self.flow = flow
        # default run name: flow directory name + timestamp
        self.name = name
        self._runtime = kwargs.get("runtime", None)
        self._resources = kwargs.get("resources", None)

    @classmethod
    def _get_schema_cls(cls):
        return FlowJobSchema


class AggregationJob(YAMLTranslatableMixin):
    def __init__(self, source, inputs, name, display_name=None, runtime=None, environment_variables=None, **kwargs):
        self.type = JobType.AGGREGATION
        self.display_name = display_name
        self.name = name
        self.source = source
        self.inputs = inputs
        self.runtime = runtime
        self.environment_variables = environment_variables or {}

    @classmethod
    def _get_schema_cls(cls):
        return AggregationJobSchema


class Orchestration(YAMLTranslatableMixin):
    def __init__(self, jobs, data=None, **kwargs):
        self.jobs = jobs
        self.data = data
        self._base_path = kwargs.get(BASE_PATH_CONTEXT_KEY, Path("."))
        self._source_path = None

    @classmethod
    def _get_schema_cls(cls):
        return OrchestrationSchema

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
        orchestration = cls._load_from_dict(
            data=data,
            context=context,
            additional_message="Failed to load orchestration",
            **kwargs,
        )
        if yaml_path:
            orchestration._source_path = yaml_path
        return orchestration

    @classmethod
    def _load_from_dict(cls, data: Dict, context: Dict, additional_message: str = None, **kwargs):
        schema_cls = cls._get_schema_cls()
        try:
            loaded_data = schema_cls(context=context).load(data, **kwargs)
        except Exception as e:
            raise Exception(f"Load orchestration failed with {str(e)}. f{(additional_message or '')}.")
        return cls(base_path=context[BASE_PATH_CONTEXT_KEY], **loaded_data)

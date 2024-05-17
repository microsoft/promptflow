# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from typing import Dict, Optional

from marshmallow import Schema

from promptflow._constants import DEFAULT_ENCODING, FLOW_TOOLS_JSON, LANGUAGE_KEY, PROMPT_FLOW_DIR_NAME, FlowLanguage
from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY
from promptflow._utils.flow_utils import is_flex_flow, is_prompty_flow, resolve_flow_path
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.yaml_utils import load_yaml, load_yaml_string
from promptflow.exceptions import ErrorTarget, UserErrorException

from .base import Flow as FlowBase

logger = get_cli_sdk_logger()


class Flow(FlowBase):
    """A FlexFlow represents an non-dag flow, which uses codes to define the flow.
    FlexFlow basically behave like a Flow, but its entry function should be provided in the flow.dag.yaml file.
    Load of this non-dag flow is provided, but direct call of it will cause exceptions.
    """

    def __init__(
        self,
        path: Path,
        code: Path,
        dag: dict,
        params_override: Optional[Dict] = None,
        **kwargs,
    ):
        super().__init__(path=path, code=code, dag=dag, **kwargs)

        # TODO: this can be dangerous. path always point to the flow yaml file; code always point to the flow directory;
        #   but path may not under code (like a temp generated flow yaml file).
        self._flow_dir, self._flow_file_name = resolve_flow_path(self.path)
        self._flow_file_path = self._flow_dir / self._flow_file_name
        self._executable = None
        self._params_override = params_override

    # region properties
    @property
    def name(self) -> str:
        return self._flow_dir.name

    @property
    def flow_dag_path(self) -> Path:
        return self._flow_file_path

    @property
    def tools_meta_path(self) -> Path:
        target_path = self._flow_dir / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON
        target_path.parent.mkdir(parents=True, exist_ok=True)
        return target_path

    @property
    def language(self) -> str:
        return self._data.get(LANGUAGE_KEY, FlowLanguage.Python)

    @property
    def additional_includes(self) -> list:
        return self._data.get("additional_includes", [])

    @property
    def display_name(self) -> str:
        return self._data.get("display_name", self._flow_dir.name)

    @property
    def sample(self):
        return self._data.get("sample", None)

    # endregion

    # region SchemaValidatableMixin
    @classmethod
    def _create_schema_for_validation(cls, context) -> "Schema":
        # import here to avoid circular import
        from promptflow._sdk.schemas._flow import FlowSchema

        return FlowSchema(context=context)

    def _default_context(self) -> dict:
        return {BASE_PATH_CONTEXT_KEY: self._flow_dir}

    def _create_validation_error(self, message, no_personal_data_message=None):
        return UserErrorException(
            message=message,
            target=ErrorTarget.CONTROL_PLANE_SDK,
            no_personal_data_message=no_personal_data_message,
        )

    def _dump_for_validation(self) -> Dict:
        # Flow is read-only in control plane, so we always dump the flow from file
        data = load_yaml(self._flow_file_path)
        if isinstance(self._params_override, dict):
            data.update(self._params_override)
        return data

    # endregion

    # region MLFlow model requirements
    @property
    def inputs(self):
        # This is used for build mlflow model signature.
        if not self._executable:
            self._executable = self._init_executable()
        return {k: v.type.value for k, v in self._executable.inputs.items()}

    @property
    def outputs(self):
        # This is used for build mlflow model signature.
        if not self._executable:
            self._executable = self._init_executable()
        return {k: v.type.value for k, v in self._executable.outputs.items()}

    # endregion

    # region overrides:
    def _init_executable(self, tuning_node=None, variant=None):
        from promptflow._sdk._orchestrator import flow_overwrite_context
        from promptflow.contracts.flow import Flow as ExecutableFlow

        if not tuning_node and not variant:
            # for DAG flow, use data to init executable to improve performance
            return super()._init_executable()

        # TODO: check if there is potential bug here
        # this is a little wired:
        # 1. the executable is created from a temp folder when there is additional includes
        # 2. after the executable is returned, the temp folder is deleted
        with flow_overwrite_context(self, tuning_node, variant) as flow:

            return ExecutableFlow.from_yaml(flow_file=flow.path, working_dir=flow.code)

    @classmethod
    def _dispatch_flow_creation(cls, flow_path, raise_error=True, **kwargs):
        """Dispatch flow load to eager flow, async flow or prompty flow."""
        from promptflow._sdk.entities._flows import FlexFlow, Prompty

        if is_prompty_flow(file_path=flow_path, raise_error=raise_error):
            return Prompty._load(path=flow_path, **kwargs)

        with open(flow_path, "r", encoding=DEFAULT_ENCODING) as f:
            flow_content = f.read()
            data = load_yaml_string(flow_content)
            content_hash = hash(flow_content)
        if is_flex_flow(yaml_dict=data):
            return FlexFlow._load(path=flow_path, data=data, raise_error=raise_error, **kwargs)
        else:
            # TODO: schema validation and warning on unknown fields
            return Flow._load(path=flow_path, dag=data, content_hash=content_hash, **kwargs)

    def invoke(self, inputs: dict) -> "LineResult":
        """Invoke a flow and get a LineResult object."""
        from promptflow._sdk._orchestrator import TestSubmitter

        if self.language == FlowLanguage.CSharp:
            # TODO 3033484: we shouldn't use context manager here for stream_output, as resource need to be released
            #  after the returned generator is fully consumed. If we use context manager here, the resource must be
            #  released before the generator is consumed.
            with TestSubmitter(flow=self, flow_context=self.context).init(
                stream_output=self.context.streaming
            ) as submitter:
                result = submitter.flow_test(inputs=inputs, allow_generator_output=self.context.streaming)
                return result
        else:
            return super().invoke(inputs=inputs)

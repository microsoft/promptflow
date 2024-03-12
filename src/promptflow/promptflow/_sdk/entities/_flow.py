# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path
from typing import Dict, Optional

from promptflow._constants import FlowLanguage
from promptflow._core._flow import AsyncFlow as AsyncFlowCore
from promptflow._core._flow import Flow as FlowCore
from promptflow._core._flow import FlowBase as FlowBaseCore
from promptflow._core._flow import FlowContext as FlowContextCore
from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY
from promptflow._sdk.entities._validation import SchemaValidatableMixin
from promptflow._utils.logger_utils import get_cli_sdk_logger
from promptflow._utils.yaml_utils import load_yaml
from promptflow.exceptions import ErrorTarget, UserErrorException

logger = get_cli_sdk_logger()

Flow = FlowCore
FlowBase = FlowBaseCore
FlowContext = FlowContextCore
AsyncFlow = AsyncFlowCore


class ProtectedFlow(FlowCore, SchemaValidatableMixin):
    """This class is used to hide internal interfaces from user.

    User interface should be carefully designed to avoid breaking changes, while developers may need to change internal
    interfaces to improve the code quality. On the other hand, making all internal interfaces private will make it
    strange to use them everywhere inside this package.

    Ideally, developers should always initialize ProtectedFlow object instead of Flow object.
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

        self._executable = None
        self._params_override = params_override

    # region SchemaValidatableMixin
    @classmethod
    def _create_schema_for_validation(cls, context) -> "Schema":
        # import here to avoid circular import
        from ..schemas._flow import FlowSchema

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
        data = load_yaml(self.flow_dag_path)
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

    # region method overrides:
    def _init_executable(self, tuning_node=None, variant=None):
        from promptflow._sdk._submitter import variant_overwrite_context
        from promptflow.contracts.flow import Flow as ExecutableFlow

        if not tuning_node and not variant:
            # for DAG flow, use data to init executable to improve performance
            return super()._init_executable()

        # TODO: check if there is potential bug here
        # this is a little wired:
        # 1. the executable is created from a temp folder when there is additional includes
        # 2. after the executable is returned, the temp folder is deleted
        with variant_overwrite_context(self, tuning_node, variant) as flow:

            return ExecutableFlow.from_yaml(flow_file=flow.path, working_dir=flow.code)

    @classmethod
    def _dispatch_flow_creation(
        cls, is_eager_flow, is_async_call, flow_path, data, content_hash, raise_error=True, **kwargs
    ):
        """Dispatch flow load to eager flow or async flow."""
        from promptflow._sdk.entities._eager_flow import EagerFlow

        if is_eager_flow:
            return EagerFlow._load(path=flow_path, data=data, raise_error=raise_error, **kwargs)
        else:
            # TODO: schema validation and warning on unknown fields
            if is_async_call:
                return AsyncProtectedFlow._load(path=flow_path, dag=data, content_hash=content_hash, **kwargs)
            else:
                return ProtectedFlow._load(path=flow_path, dag=data, content_hash=content_hash, **kwargs)

    def invoke(self, inputs: dict) -> "LineResult":
        """Invoke a flow and get a LineResult object."""
        from promptflow._sdk._submitter import TestSubmitter

        if self.language == FlowLanguage.CSharp:
            with TestSubmitter(flow=self, flow_context=self.context).init(
                stream_output=self.context.streaming
            ) as submitter:
                result = submitter.flow_test(inputs=inputs, allow_generator_output=self.context.streaming)
                return result
        else:
            return super().invoke(inputs=inputs)

    # endregion


class AsyncProtectedFlow(ProtectedFlow, AsyncFlowCore):
    """This class is used to represent an async protected flow."""

    async def invoke_async(self, inputs: dict) -> "LineResult":
        """Invoke a flow and get a LineResult object."""
        from promptflow._sdk._submitter import TestSubmitter

        if self.language == FlowLanguage.CSharp:
            # Sync C# calling
            # TODO: Async C# support: Task(3002242)
            with TestSubmitter(flow=self, flow_context=self.context).init(
                stream_output=self.context.streaming
            ) as submitter:
                result = submitter.flow_test(inputs=inputs, allow_generator_output=self.context.streaming)
                return result
        else:
            return await super().invoke_async(inputs=inputs)

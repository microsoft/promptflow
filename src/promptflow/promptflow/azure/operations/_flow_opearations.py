# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import re
from pathlib import Path
# pylint: disable=protected-access
from typing import Dict, Any

from azure.ai.ml._scope_dependent_operations import (
    OperationConfig,
    OperationsContainer,
    OperationScope,
    _ScopeDependentOperations,
)
from azure.ai.ml._utils._storage_utils import AzureMLDatastorePathUri
from azure.ai.ml._utils.utils import hash_dict
from azure.ai.ml.constants._common import AzureMLResourceType
from azure.ai.ml.operations import WorkspaceOperations, ComponentOperations
from azure.ai.ml.operations._code_operations import CodeOperations
from azure.ai.ml.operations._operation_orchestrator import OperationOrchestrator

from promptflow.azure._ml import Component
from promptflow.azure._restclient.flow.models import LoadFlowAsComponentRequest, FlowRunMode
from promptflow.azure._utils import is_arm_id
from promptflow.azure.entities._flow import Flow
from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
from promptflow.azure.constants._flow import DEFAULT_STORAGE


class FlowOperations(_ScopeDependentOperations):
    """FlowOperations.

    You should not instantiate this class directly. Instead, you should
    create an MLClient instance that instantiates it for you and
    attaches it as an attribute.
    """

    def __init__(
            self,
            operation_scope: OperationScope,
            operation_config: OperationConfig,
            all_operations: OperationsContainer,
            credential,
            **kwargs: Dict,
    ):
        super(FlowOperations, self).__init__(operation_scope, operation_config)
        self._all_operations = all_operations
        workspace = self._workspace_operations.get(name=operation_scope.workspace_name)
        self._service_caller = FlowServiceCaller(workspace, credential)
        self._credential = credential

    @property
    def _code_operations(self) -> CodeOperations:
        return self._all_operations.get_operation(AzureMLResourceType.CODE, lambda x: isinstance(x, CodeOperations))

    @property
    def _workspace_operations(self) -> WorkspaceOperations:
        return self._all_operations.get_operation(
            AzureMLResourceType.WORKSPACE, lambda x: isinstance(x, WorkspaceOperations)
        )

    def create_or_update(
            self,
            flow,
            **kwargs
    ):
        # upload to file share
        self._resolve_arm_id_or_upload_dependencies(flow)

        rest_flow = flow._to_rest_object()

        # create flow draft
        rest_flow_result = self._service_caller.create_flow(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            body=rest_flow,
        )

        return rest_flow_result

    def get(self, flow_id):
        # TODO: support load remote flow with meta
        raise NotImplemented("Not implemented yet")

    def list(self, **kwargs):
        rest_flow_result = self._service_caller.list_flows(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
        )
        # note that the service may return flow rest obj with no flow name
        flows = [Flow._from_rest_object(rest_flow) for rest_flow in rest_flow_result if rest_flow.flow_name]
        flows = sorted(flows, key=lambda x: x.name)
        return flows

    def download(self, source, dest):
        # TODO: support download flow
        raise NotImplemented("Not implemented yet")

    @classmethod
    def clear_empty_item(cls, obj):
        if not isinstance(obj, dict):
            return obj
        return {k: cls.clear_empty_item(v) for k, v in obj.items() if v is not None}

    @classmethod
    def _get_component_hash(cls, rest_object):
        """this hash should include all the burn-in information:
        - code
        - keys of inputs_mapping
        - environment_variables, it will be burned into something like component.task.environment_variables?
        some other fields will be burned into component but will impact default value of inputs:
        - variant
        - connections
        - values of inputs_mapping
        Now we use all of them as hash key.
        """
        obj = rest_object.as_dict()

        return hash_dict(cls.clear_empty_item(obj))

    @classmethod
    def _get_name_and_version(cls, *, rest_object, name: str = None, version: str = None):
        # TODO: confirm the logic for name and version, key problem is about reuse
        if name and version:
            return name, version
        if name or version:
            raise ValueError("name and version of the component must be provided together")
        # TODO: update this after MT support creating component with same name and different version
        return "azureml_promptflow_" + cls._get_component_hash(rest_object).replace("-", "_"), "1"

    def load_as_component(
        self,
        flow,
        name: str = None,
        version: str = None,
        display_name: str = None,
        description: str = None,
        tags: Dict[str, str] = None,
        variant: str = None,
        columns_mapping: Dict[str, str] = None,
        environment_variables: Dict[str, Any] = None,
        connections: Dict[str, Dict[str, str]] = None,
        is_deterministic: bool = True,
        **kwargs
    ) -> Component:
        rest_object = LoadFlowAsComponentRequest(
            node_variant=variant,
            inputs_mapping=columns_mapping,
            environment_variables=environment_variables,
            connections=connections,
            display_name=display_name,
            description=description,
            tags=tags,
            is_deterministic=is_deterministic,
            # hack: MT support this only for now, will remove after MT release new version
            run_mode=FlowRunMode.BULK_TEST,
        )

        if is_arm_id(flow):
            rest_object.flow_definition_resource_id = flow.id
        else:
            # upload to file share
            self._resolve_arm_id_or_upload_dependencies(flow)
            # TODO: current remote path looks a little weird: Users/xxx/Promptflows\\web_classification
            #  should it starts with azureml:// and with a hash in the path?
            rest_object.flow_definition_file_path = flow.path

        rest_object.component_name, rest_object.component_version = self._get_name_and_version(
            rest_object=rest_object, name=name, version=version
        )

        component_id = self._service_caller.create_component_from_flow(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            body=rest_object,
        )
        name, version = re.match(r".*/components/(.*)/versions/(.*)", component_id).groups()
        return self._all_operations.get_operation(
            AzureMLResourceType.COMPONENT,
            lambda x: isinstance(x, ComponentOperations),
        ).get(name, version)

    def _resolve_arm_id_or_upload_dependencies(self, flow: Flow) -> None:

        ops = OperationOrchestrator(self._all_operations, self._operation_scope, self._operation_config)
        # resolve flow's code
        self._try_resolve_code_for_flow(flow=flow, ops=ops)

    @classmethod
    def _try_resolve_code_for_flow(cls, flow: Flow, ops: OperationOrchestrator) -> None:
        from ._artifact_utilities import _check_and_upload_path

        if flow.path:
            if flow.path.startswith("azureml://datastores"):
                # remote path
                path_uri = AzureMLDatastorePathUri(flow.path)
                if path_uri.datastore != DEFAULT_STORAGE:
                    raise ValueError(f"Only {DEFAULT_STORAGE} is supported as remote storage for now.")
                flow.path = path_uri.path
                flow._code_uploaded = True
                return
        else:
            raise ValueError("Path is required for flow.")

        with flow._resolve_local_code() as code:
            if code is None:
                return
            if flow._code_uploaded:
                return

            uploaded_code_asset = _check_and_upload_path(
                artifact=code,
                asset_operations=ops._code_assets,
                artifact_type="Code",
                show_progress=False,
            )
            if "remote_path" in uploaded_code_asset:
                path = uploaded_code_asset["remote_path"]
            elif "remote path" in uploaded_code_asset:
                path = uploaded_code_asset["remote path"]
            flow.code = path
            flow.path = (Path(path) / flow.path).as_posix()
            flow._code_uploaded = True

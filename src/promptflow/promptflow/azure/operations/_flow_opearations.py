# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# pylint: disable=protected-access

import json
import re
from pathlib import Path
from typing import Any, Dict

import yaml
from azure.ai.ml._artifacts._artifact_utilities import _check_and_upload_path
from azure.ai.ml._scope_dependent_operations import (
    OperationConfig,
    OperationsContainer,
    OperationScope,
    _ScopeDependentOperations,
)
from azure.ai.ml._utils._storage_utils import AzureMLDatastorePathUri
from azure.ai.ml._utils.utils import hash_dict
from azure.ai.ml.constants._common import SHORT_URI_FORMAT, AzureMLResourceType
from azure.ai.ml.operations import ComponentOperations, WorkspaceOperations
from azure.ai.ml.operations._code_operations import CodeOperations
from azure.ai.ml.operations._operation_orchestrator import OperationOrchestrator
from azure.core.exceptions import HttpResponseError

from promptflow._sdk._constants import (
    DAG_FILE_NAME,
    FLOW_TOOLS_JSON,
    NODE,
    NODE_VARIANTS,
    NODES,
    USE_VARIANTS,
    VARIANTS,
    WORKSPACE_LINKED_DATASTORE_NAME,
)
from promptflow._utils.context_utils import _change_working_dir, inject_sys_path
from promptflow._utils.generate_tool_meta_utils import (
    generate_prompt_meta,
    generate_python_meta,
)
from promptflow.azure._constants._flow import DEFAULT_STORAGE
from promptflow.azure._entities._flow import Flow
from promptflow.azure._ml import Component
from promptflow.azure._restclient.flow.models import (
    FlowRunMode,
    LoadFlowAsComponentRequest,
)
from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
from promptflow.azure._utils import is_arm_id
from promptflow.contracts.tool import ToolType


class FlowOperations(_ScopeDependentOperations):
    """FlowOperations.

    You should not instantiate this class directly. Instead, you should
    create an MLClient instance that instantiates it for you and
    attaches it as an attribute
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
        self._service_caller = FlowServiceCaller(workspace, credential, **kwargs)
        self._credential = credential

    @property
    def _code_operations(self) -> CodeOperations:
        return self._all_operations.get_operation(
            AzureMLResourceType.CODE, lambda x: isinstance(x, CodeOperations)
        )

    @property
    def _workspace_operations(self) -> WorkspaceOperations:
        return self._all_operations.get_operation(
            AzureMLResourceType.WORKSPACE, lambda x: isinstance(x, WorkspaceOperations)
        )

    def _create_or_update(self, flow, **kwargs):
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

    def _get(self, flow_id):
        # TODO: support load remote flow with meta
        raise NotImplementedError("Not implemented yet")

    def _list(self, **kwargs):
        rest_flow_result = self._service_caller.list_flows(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
        )
        # note that the service may return flow rest obj with no flow name
        flows = [
            Flow._from_rest_object(rest_flow)
            for rest_flow in rest_flow_result
            if rest_flow.flow_name
        ]
        flows = sorted(flows, key=lambda x: x.name)
        return flows

    def _download(self, source, dest):
        # TODO: support download flow
        raise NotImplementedError("Not implemented yet")

    @classmethod
    def _clear_empty_item(cls, obj):
        if not isinstance(obj, dict):
            return obj
        return {k: cls._clear_empty_item(v) for k, v in obj.items() if v is not None}

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

        return hash_dict(cls._clear_empty_item(obj))

    @classmethod
    def _get_name_and_version(
        cls, *, rest_object, name: str = None, version: str = None
    ):
        if name and version:
            return name, version
        if name or version:
            raise ValueError(
                "name and version of the component must be provided together"
            )
        # the hash will be impacted by all editable fields, including default value of inputs_mapping
        # so components with different default value of columns_mapping can't be reused from each other
        return "azureml_anonymous_flow", cls._get_component_hash(rest_object)

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
        **kwargs,
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
            if flow.path.startswith("azureml://"):
                # upload via _check_and_upload_path
                # submit with params FlowDefinitionDataStoreName and FlowDefinitionBlobPath
                path_uri = AzureMLDatastorePathUri(flow.path)
                rest_object.flow_definition_data_store_name = path_uri.datastore
                rest_object.flow_definition_blob_path = path_uri.path
            else:
                # upload via CodeOperations.create_or_update
                # submit with param FlowDefinitionDataUri
                rest_object.flow_definition_data_uri = flow.path

        (
            rest_object.component_name,
            rest_object.component_version,
        ) = self._get_name_and_version(
            rest_object=rest_object, name=name, version=version
        )

        component_id = self._service_caller.create_component_from_flow(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            body=rest_object,
        )
        name, version = re.match(
            r".*/components/(.*)/versions/(.*)", component_id
        ).groups()
        return self._all_operations.get_operation(
            AzureMLResourceType.COMPONENT,
            lambda x: isinstance(x, ComponentOperations),
        ).get(name, version)

    def _resolve_arm_id_or_upload_dependencies_to_file_share(self, flow: Flow) -> None:
        ops = OperationOrchestrator(
            self._all_operations, self._operation_scope, self._operation_config
        )
        # resolve flow's code
        self._try_resolve_code_for_flow_to_file_share(flow=flow, ops=ops)

    @classmethod
    def _try_resolve_code_for_flow_to_file_share(
        cls, flow: Flow, ops: OperationOrchestrator
    ) -> None:
        from ._artifact_utilities import _check_and_upload_path

        if flow.path:
            if flow.path.startswith("azureml://datastores"):
                # remote path
                path_uri = AzureMLDatastorePathUri(flow.path)
                if path_uri.datastore != DEFAULT_STORAGE:
                    raise ValueError(
                        f"Only {DEFAULT_STORAGE} is supported as remote storage for now."
                    )
                flow.path = path_uri.path
                flow._code_uploaded = True
                return
        else:
            raise ValueError("Path is required for flow.")

        with flow._build_code() as code:
            if code is None:
                return
            if flow._code_uploaded:
                return
            code.datastore = DEFAULT_STORAGE
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

    def _resolve_arm_id_or_upload_dependencies(self, flow: Flow) -> None:
        ops = OperationOrchestrator(
            self._all_operations, self._operation_scope, self._operation_config
        )
        # resolve flow's code
        self._try_resolve_code_for_flow(flow=flow, ops=ops)

    @classmethod
    def _try_resolve_code_for_flow(cls, flow: Flow, ops: OperationOrchestrator) -> None:
        if flow.path:
            # remote path
            if flow.path.startswith("azureml://datastores"):
                flow._code_uploaded = True
                return
        else:
            raise ValueError("Path is required for flow.")

        with flow._build_code() as code:
            if code is None:
                return
            if flow._code_uploaded:
                return

            # TODO(2567532): backend does not fully support generate flow.tools.json from blob storage yet
            if not (Path(code.path) / ".promptflow" / FLOW_TOOLS_JSON).exists():
                cls._generate_flow_tools_json(code.path)

            code.datastore = WORKSPACE_LINKED_DATASTORE_NAME
            # NOTE: For flow directory upload, we prefer to upload it to the workspace linked datastore,
            # therefore we will directly use _check_and_upload_path, instead of v2 SDK public API
            # CodeOperations.create_or_update, as later one will upload the code asset to another
            # container in the storage account, which may fail with vnet for MT.
            # However, we might run into list secret permission error(especially in Heron workspace),
            # in this case, we will leverage v2 SDK public API, which has solution for Heron,
            # and request MT with the blob url;
            # refer to except block for more details.
            try:
                uploaded_code_asset, _ = _check_and_upload_path(
                    artifact=code,
                    asset_operations=ops._code_assets,
                    artifact_type="Code",
                    datastore_name=WORKSPACE_LINKED_DATASTORE_NAME,  # actually not work at all
                    show_progress=False,
                )
                path = uploaded_code_asset.path
                path = path[path.find("LocalUpload") :]  # path on container
                flow.code = path
                # azureml://datastores/workspaceblobstore/paths/<path-to-flow-dag-yaml>
                flow.path = SHORT_URI_FORMAT.format(
                    WORKSPACE_LINKED_DATASTORE_NAME, (Path(path) / flow.path).as_posix()
                )
            except HttpResponseError as e:
                # catch authorization error for list secret on datastore
                if "AuthorizationFailed" in str(
                    e
                ) and "datastores/listSecrets/action" in str(e):
                    uploaded_code_asset = ops._code_assets.create_or_update(code)
                    path = uploaded_code_asset.path
                    path = path.replace(
                        ".blob.core.windows.net:443/", ".blob.core.windows.net/"
                    )  # remove :443 port
                    flow.code = path
                    # https://<storage-account-name>.blob.core.windows.net/<container-name>/<path-to-flow-dag-yaml>
                    flow.path = f"{path}/{flow.path}"
                else:
                    raise
            flow._code_uploaded = True

    @staticmethod
    def _generate_flow_tools_json(flow_directory) -> None:
        flow_directory = Path(flow_directory)
        # Copy logic from PFS and runtime.
        # PFS - GetGenerateToolMetaRequestToRuntime
        with open(flow_directory / DAG_FILE_NAME, "r") as f:
            data = yaml.safe_load(f)
        tools = []
        for node in data[NODES]:
            if "source" in node:
                if node["source"]["type"] != "code":
                    continue
                if not (flow_directory / node["source"]["path"]).exists():
                    continue
                tools.append((node["source"]["path"], node["type"].lower()))
            # understand DAG to parse variants
            elif node.get(USE_VARIANTS) is True:
                node_variants = data[NODE_VARIANTS][node["name"]]
                for variant_id in node_variants[VARIANTS]:
                    current_node = node_variants[VARIANTS][variant_id][NODE]
                    if current_node["source"]["type"] != "code":
                        continue
                    if not (flow_directory / current_node["source"]["path"]).exists():
                        continue
                    tools.append(
                        (current_node["source"]["path"], current_node["type"].lower())
                    )
        # runtime - meta_v2
        tools_dict = {}
        for tool_path, node_type in tools:
            with _change_working_dir(flow_directory), inject_sys_path(flow_directory):
                tool_file = flow_directory / tool_path
                content = tool_file.read_text()
                if node_type == ToolType.LLM:
                    result = generate_prompt_meta(tool_path, content, source=tool_path)
                elif node_type == ToolType.PROMPT:
                    result = generate_prompt_meta(
                        tool_path, content, prompt_only=True, source=tool_path
                    )
                else:
                    result = generate_python_meta(tool_path, content, source=tool_path)
                tools_dict[tool_path] = json.loads(result)
        # PFS - DownloadSnapshotAndGenTools
        flow_tools = {
            # TODO(zhengfeiwang): we might need to copy PFS/runtime logic for package too
            "package": {},
            "code": tools_dict,
        }
        # dump flow.tools.json
        promptflow_folder = flow_directory / ".promptflow"
        promptflow_folder.mkdir(exist_ok=True)
        with open(promptflow_folder / FLOW_TOOLS_JSON, "w") as f:
            json.dump(flow_tools, f, indent=4)
        return

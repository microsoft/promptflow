# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# pylint: disable=protected-access

import logging
import os
from pathlib import Path
from typing import Dict

from azure.ai.ml._artifacts._artifact_utilities import _check_and_upload_path
from azure.ai.ml._scope_dependent_operations import (
    OperationConfig,
    OperationsContainer,
    OperationScope,
    _ScopeDependentOperations,
)
from azure.ai.ml.constants._common import SHORT_URI_FORMAT
from azure.ai.ml.operations._operation_orchestrator import OperationOrchestrator
from azure.core.exceptions import HttpResponseError

from promptflow._sdk._constants import (
    FLOW_TOOLS_JSON,
    LOGGER_NAME,
    PROMPT_FLOW_DIR_NAME,
    WORKSPACE_LINKED_DATASTORE_NAME,
)
from promptflow._sdk._utils import PromptflowIgnoreFile, generate_flow_tools_json
from promptflow._sdk._vendor._asset_utils import traverse_directory
from promptflow.azure._entities._flow import Flow
from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
from promptflow.exceptions import SystemErrorException


class FlowOperations(_ScopeDependentOperations):
    """FlowOperations that can manage flows.

    You should not instantiate this class directly. Instead, you should
    create an PFClient instance that instantiates it for you and
    attaches it as an attribute.
    """

    def __init__(
        self,
        operation_scope: OperationScope,
        operation_config: OperationConfig,
        all_operations: OperationsContainer,
        credential,
        service_caller: FlowServiceCaller,
        **kwargs: Dict,
    ):
        super(FlowOperations, self).__init__(operation_scope, operation_config)
        self._all_operations = all_operations
        self._service_caller = service_caller
        self._credential = credential

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
        flows = [Flow._from_rest_object(rest_flow) for rest_flow in rest_flow_result if rest_flow.flow_name]
        flows = sorted(flows, key=lambda x: x.name)
        return flows

    def _download(self, source, dest):
        # TODO: support download flow
        raise NotImplementedError("Not implemented yet")

    def _resolve_arm_id_or_upload_dependencies(self, flow: Flow, ignore_tools_json=False) -> None:
        ops = OperationOrchestrator(self._all_operations, self._operation_scope, self._operation_config)
        # resolve flow's code
        self._try_resolve_code_for_flow(flow=flow, ops=ops, ignore_tools_json=ignore_tools_json)

    @classmethod
    def _try_resolve_code_for_flow(cls, flow: Flow, ops: OperationOrchestrator, ignore_tools_json=False) -> None:
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
            if not (Path(code.path) / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON).exists():
                generate_flow_tools_json(code.path)
            # ignore flow.tools.json if needed (e.g. for flow run scenario)
            if ignore_tools_json:
                ignore_file = code._ignore_file
                if isinstance(ignore_file, PromptflowIgnoreFile):
                    ignore_file._ignore_tools_json = ignore_tools_json
                else:
                    raise SystemErrorException(
                        message=f"Flow code should have PromptflowIgnoreFile, got {type(ignore_file)}"
                    )

            # flow directory per file upload summary
            # as the upload logic locates in azure-ai-ml, we cannot touch during the upload
            # copy the logic here to print per file upload summary
            ignore_file = code._ignore_file
            upload_paths = []
            source_path = Path(code.path).resolve()
            prefix = os.path.basename(source_path) + "/"
            for root, _, files in os.walk(source_path, followlinks=True):
                upload_paths += list(
                    traverse_directory(
                        root,
                        files,
                        prefix=prefix,
                        ignore_file=ignore_file,
                    )
                )
            logger = logging.getLogger(LOGGER_NAME)
            for file_path, _ in upload_paths:
                logger.debug(f"will upload file: {file_path}...")

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
                    show_progress=True,
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
                if "AuthorizationFailed" in str(e) and "datastores/listSecrets/action" in str(e):
                    uploaded_code_asset = ops._code_assets.create_or_update(code)
                    path = uploaded_code_asset.path
                    path = path.replace(".blob.core.windows.net:443/", ".blob.core.windows.net/")  # remove :443 port
                    flow.code = path
                    # https://<storage-account-name>.blob.core.windows.net/<container-name>/<path-to-flow-dag-yaml>
                    flow.path = f"{path}/{flow.path}"
                else:
                    raise
            flow._code_uploaded = True

    # region deprecated but keep for runtime test dependencies
    def _resolve_arm_id_or_upload_dependencies_to_file_share(self, flow: Flow) -> None:
        ops = OperationOrchestrator(self._all_operations, self._operation_scope, self._operation_config)
        # resolve flow's code
        self._try_resolve_code_for_flow_to_file_share(flow=flow, ops=ops)

    @classmethod
    def _try_resolve_code_for_flow_to_file_share(cls, flow: Flow, ops: OperationOrchestrator) -> None:
        from azure.ai.ml._utils._storage_utils import AzureMLDatastorePathUri

        from promptflow.azure._constants._flow import DEFAULT_STORAGE

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

    # endregion

# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
# pylint: disable=protected-access

import logging
import os
import re
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Dict, Union

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
    CLIENT_FLOW_TYPE_2_SERVICE_FLOW_TYPE,
    DAG_FILE_NAME,
    FLOW_TOOLS_JSON,
    LOGGER_NAME,
    PROMPT_FLOW_DIR_NAME,
    WORKSPACE_LINKED_DATASTORE_NAME,
    FlowType,
)
from promptflow._sdk._errors import FlowOperationError
from promptflow._sdk._logger_factory import LoggerFactory
from promptflow._sdk._utils import PromptflowIgnoreFile, generate_flow_tools_json
from promptflow._sdk._vendor._asset_utils import traverse_directory
from promptflow._telemetry.activity import ActivityType, monitor_operation
from promptflow.azure._constants._flow import DEFAULT_STORAGE
from promptflow.azure._entities._flow import Flow as AzureFlow
from promptflow.azure._load_functions import load_flow as load_azure_flow
from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller
from promptflow.azure.operations._artifact_utilities import _get_datastore_name, get_datastore_info
from promptflow.azure.operations._fileshare_storeage_helper import FlowFileStorageClient
from promptflow.exceptions import SystemErrorException

logger = LoggerFactory.get_logger(name=LOGGER_NAME, verbosity=logging.WARNING)


class FlowOperations(_ScopeDependentOperations):
    """FlowOperations that can manage flows.

    You should not instantiate this class directly. Instead, you should
    create a :class:`~promptflow.azure.PFClient` instance that instantiates it for you and
    attaches it as an attribute.
    """

    _FLOW_RESOURCE_PATTERN = re.compile(r"azureml:.*?/workspaces/(?P<datastore>.*?)/flows/(?P<flow_id>.*?)$")

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

    @cached_property
    def _common_azure_url_pattern(self):
        operation_scope = self._operation_scope
        url = (
            f"/subscriptions/{operation_scope.subscription_id}"
            f"/resourceGroups/{operation_scope.resource_group_name}"
            f"/providers/Microsoft.MachineLearningServices"
            f"/workspaces/{operation_scope.workspace_name}"
        )
        return url

    def _get_flow_portal_url(self, flow_resource_id: str):
        """Get the portal url for the run."""
        match = self._FLOW_RESOURCE_PATTERN.match(flow_resource_id)
        if not match or len(match.groups()) != 2:
            logger.warning("Failed to parse flow resource id '%s'", flow_resource_id)
            return None
        datastore, flow_id = match.groups()
        url = f"https://ml.azure.com/prompts/flow/{datastore}/{flow_id}/details?wsid={self._common_azure_url_pattern}"
        return url

    @monitor_operation(activity_name="pfazure.flows.create_or_update", activity_type=ActivityType.PUBLICAPI)
    def create_or_update(self, source: Union[str, Path], flow_name=None, flow_type=None, **kwargs) -> AzureFlow:
        """Create a flow to remote from local source.

        :param source: The source of the flow to create.
        :type source: Union[str, Path]
        :param flow_name: The name of the flow to create. Default to be flow folder name + timestamp if not specified.
            e.g. "web-classification-10-27-2023-14-19-10"
        :type flow_name: str
        :param flow_type: The type of the flow to create. One of ["standard", evaluation", "chat"].
            Default to be "standard" if not specified.
        :type flow_type: str
        :param description: The description of the flow to create. Default to be the description in flow yaml file.
        :type description: str
        :param tags: The tags of the flow to create. Default to be the tags in flow yaml file.
        :type tags: Dict[str, str]
        """
        # validate the parameters
        azure_flow, flow_name, flow_type, kwargs = self._validate_flow_creation_parameters(
            source, flow_name, flow_type, **kwargs
        )
        # upload to file share
        file_share_flow_path = self._resolve_flow_code_and_upload_to_file_share(flow=azure_flow, flow_name=flow_name)
        if not file_share_flow_path:
            raise FlowOperationError(f"File share path should not be empty, got {file_share_flow_path!r}.")

        # create flow to remote
        flow_definition_file_path = f"{file_share_flow_path}/{DAG_FILE_NAME}"
        rest_flow = self._create_remote_flow_via_file_share_path(
            flow_name=flow_name,
            flow_type=flow_type,
            flow_definition_file_path=flow_definition_file_path,
            **kwargs,
        )
        flow_portal_url = self._get_flow_portal_url(rest_flow.flow_resource_id)
        print(f"Flow created successfully, flow portal url:\n{flow_portal_url}")

        return azure_flow

    def _validate_flow_creation_parameters(self, source, flow_name, flow_type, **kwargs):
        """Validate the parameters for flow creation operation."""
        flow = load_azure_flow(source)
        # if no flow name specified, use "flow name + timestamp"
        if not flow_name:
            flow_name = f"{flow.name}-{datetime.now().strftime('%m-%d-%Y-%H-%M-%S')}"

        # if no flow type specified, use default flow type "standard"
        supported_flow_types = FlowType.get_all_values()
        if not flow_type:
            flow_type = FlowType.STANDARD
        elif flow_type not in supported_flow_types:
            raise FlowOperationError(
                f"Flow type {flow_type!r} is not supported, supported types are {supported_flow_types}"
            )

        # check description type
        description = kwargs.get("description", None) or flow.description

        if isinstance(description, str):
            kwargs["description"] = description
        elif description is not None:
            logger.warning(f"Description must be a string, got {type(description)!r}: {description!r}.")

        # check if the tags type is Dict[str, str]
        tags = kwargs.get("tags", None) or flow.tags
        if isinstance(tags, dict) and all(
            isinstance(key, str) and isinstance(value, str) for key, value in tags.items()
        ):
            kwargs["tags"] = tags
        elif tags is not None:
            logger.warning(f"Tags type must be 'Dict[str, str]', got non-dict or non-string key/value in tags: {tags}.")

        return flow, flow_name, flow_type, kwargs

    def _resolve_flow_code_and_upload_to_file_share(
        self, flow: AzureFlow, flow_name: str, ignore_tools_json=True
    ) -> str:
        ops = OperationOrchestrator(self._all_operations, self._operation_scope, self._operation_config)
        file_share_flow_path = ""

        with flow._build_code() as code:
            if code is None:
                raise FlowOperationError("Failed to build flow code.")

            # ignore flow.tools.json if needed (e.g. for flow run scenario)
            if ignore_tools_json:
                ignore_file = code._ignore_file
                if isinstance(ignore_file, PromptflowIgnoreFile):
                    ignore_file._ignore_tools_json = ignore_tools_json
                else:
                    raise FlowOperationError(
                        message=f"Flow code should have PromptflowIgnoreFile, got {type(ignore_file)}"
                    )

            code.datastore = DEFAULT_STORAGE

            datastore_name = _get_datastore_name(datastore_name=DEFAULT_STORAGE)
            datastore_operation = ops._code_assets._datastore_operation
            datastore_info = get_datastore_info(datastore_operation, datastore_name)
            storage_client = FlowFileStorageClient(
                credential=datastore_info["credential"],
                file_share_name=datastore_info["container_name"],
                account_url=datastore_info["account_url"],
                azure_cred=datastore_operation._credential,
            )
            logger.debug("Created storage client for uploading flow to file share.")

            # check if the file share directory exists
            if storage_client._check_file_share_directory_exist(flow_name):
                raise FlowOperationError(
                    f"Remote flow folder {flow_name!r} already exists under '{storage_client.file_share_prefix}'. "
                    f"Please change the flow folder name and try again."
                )

            try:
                storage_client.upload_dir(
                    source=code.path,
                    dest=flow_name,
                    msg="test",
                    ignore_file=code._ignore_file,
                    show_progress=False,
                )
            except Exception as e:
                raise FlowOperationError(f"Failed to upload flow to file share due to: {str(e)}.") from e

            file_share_flow_path = f"{storage_client.file_share_prefix}/{flow_name}"
            logger.info(f"Successfully uploaded flow to file share path {file_share_flow_path!r}.")
        return file_share_flow_path

    def _create_remote_flow_via_file_share_path(self, flow_name, flow_type, flow_definition_file_path, **kwargs):
        """Create a flow to remote from file share path."""
        service_flow_type = CLIENT_FLOW_TYPE_2_SERVICE_FLOW_TYPE[flow_type]
        description = kwargs.get("description", None)
        tags = kwargs.get("tags", None)
        body = {
            "flow_name": flow_name,
            "flow_definition_file_path": flow_definition_file_path,
            "flow_type": service_flow_type,
            "description": description,
            "tags": tags,
        }
        rest_flow_result = self._service_caller.create_flow(
            subscription_id=self._operation_scope.subscription_id,
            resource_group_name=self._operation_scope.resource_group_name,
            workspace_name=self._operation_scope.workspace_name,
            body=body,
        )
        return rest_flow_result

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
        flows = [AzureFlow._from_rest_object(rest_flow) for rest_flow in rest_flow_result if rest_flow.flow_name]
        flows = sorted(flows, key=lambda x: x.name)
        return flows

    def _download(self, source, dest):
        # TODO: support download flow
        raise NotImplementedError("Not implemented yet")

    def _resolve_arm_id_or_upload_dependencies(self, flow: AzureFlow, ignore_tools_json=False) -> None:
        ops = OperationOrchestrator(self._all_operations, self._operation_scope, self._operation_config)
        # resolve flow's code
        self._try_resolve_code_for_flow(flow=flow, ops=ops, ignore_tools_json=ignore_tools_json)

    @classmethod
    def _try_resolve_code_for_flow(cls, flow: AzureFlow, ops: OperationOrchestrator, ignore_tools_json=False) -> None:
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
    def _resolve_arm_id_or_upload_dependencies_to_file_share(self, flow: AzureFlow) -> None:
        ops = OperationOrchestrator(self._all_operations, self._operation_scope, self._operation_config)
        # resolve flow's code
        self._try_resolve_code_for_flow_to_file_share(flow=flow, ops=ops)

    @classmethod
    def _try_resolve_code_for_flow_to_file_share(cls, flow: AzureFlow, ops: OperationOrchestrator) -> None:
        from azure.ai.ml._utils._storage_utils import AzureMLDatastorePathUri

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

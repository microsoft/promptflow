import re
import os
from typing import Any
from azure.identity import DefaultAzureCredential
from azure.ai.ml import MLClient
from azure.ai.ml._artifacts._artifact_utilities import (
    download_artifact_from_aml_uri,
    aml_datastore_path_exists,
    get_datastore_info
)

from .global_instance_manager import GlobalInstanceManager
from .path_utils import PathUtils, WorkspaceInfo


AML_WORKSPACE_BLOB_STORE_NAME = "workspaceblobstore"
KEY_VAULT_RESOURCE_ID_REGEX_FORMAT = (
    r"vaults\/(.+?)($|\/)"
)


class MLClientManager(GlobalInstanceManager):

    def get_instance(
        self,
        workspace_info: WorkspaceInfo,
        credential: Any = None
    ) -> MLClient:
        workspace_identifier = workspace_info.to_tuple()
        return super()._get_instance(
            identifier=workspace_identifier,
            workspace_info=workspace_info,
            credential=credential
        )

    def _create_instance(self, workspace_info: WorkspaceInfo, credential: Any) -> Any:
        if not credential:
            credential = DefaultAzureCredential()
        return MLClient(
            credential=credential,
            subscription_id=workspace_info.subscription_id,
            resource_group_name=workspace_info.resource_group,
            workspace_name=workspace_info.workspace_name
        )


class AmlAgent:

    def __init__(self, workspace_info: WorkspaceInfo, credential: any = None):

        if credential is None:
            credential = DefaultAzureCredential()

        manager: MLClientManager = MLClientManager()
        self.__client = manager.get_instance(
            workspace_info=workspace_info,
            credential=credential
        )

    @property
    def client(self) -> MLClient:
        return self.__client

    def is_datastore_path_exists(self, url: str) -> bool:
        return aml_datastore_path_exists(
            url,
            self.__client.datastores
        )

    def download_from_datastore_url(self,
                                    url: str,
                                    destination: str):
        download_artifact_from_aml_uri(
            uri=url,
            destination=destination,
            datastore_operation=self.__client.datastores
        )

    def get_key_vault(self):

        ws = self.__client.workspaces.get()

        vault_name = re.search(
            KEY_VAULT_RESOURCE_ID_REGEX_FORMAT,
            str(ws.key_vault)
        ).group(1)

        vault_url = f"https://{vault_name}.vault.azure.net/"

        from azure.keyvault.secrets import SecretClient
        return SecretClient(
            vault_url=vault_url,
            credential=DefaultAzureCredential()
        )

    def is_blob_on_workspace_default_storage(self, blob_url: str) -> bool:
        blob_info = PathUtils.parse_blob_url(blob_url)
        default_storage_account = self.__client.workspaces.get().storage_account
        account_name = os.path.basename(default_storage_account)
        return blob_info.account_name == account_name

    def get_default_storage_credential(self) -> str:
        return str(get_datastore_info(self.__client.datastores, AML_WORKSPACE_BLOB_STORE_NAME)['credential'])

    def get_url_for_relative_path_on_workspace_blob_store(self, path: str) -> str:
        datastore_info = get_datastore_info(self.__client.datastores, AML_WORKSPACE_BLOB_STORE_NAME)
        container_url = PathUtils.url_join(datastore_info['account_url'], datastore_info['container_name'])
        return PathUtils.url_join(container_url, path)

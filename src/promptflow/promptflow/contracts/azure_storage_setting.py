from dataclasses import dataclass

from ..utils._runtime_contract_util import normalize_dict_keys_camel_to_snake
from .azure_storage_mode import AzureStorageMode


@dataclass
class AzureStorageSetting:
    """Settings for Azure Storage"""

    azure_storage_mode: AzureStorageMode = AzureStorageMode.Table
    storage_account_name: str = None
    blob_container_name: str = None
    flow_artifacts_root_path: str = None
    blob_container_sas_token: str = None
    output_datastore_name: str = None

    @staticmethod
    def deserialize(data: dict) -> "AzureStorageSetting":
        data = normalize_dict_keys_camel_to_snake(data)

        azure_storage_setting = AzureStorageSetting(
            azure_storage_mode=AzureStorageMode.parse(data.get("azure_storage_mode", AzureStorageMode.Table)),
            storage_account_name=data.get("storage_account_name", ""),
            blob_container_name=data.get("blob_container_name", ""),
            flow_artifacts_root_path=data.get("flow_artifacts_root_path", ""),
            blob_container_sas_token=data.get("blob_container_sas_token", ""),
            output_datastore_name=data.get("output_datastore_name", ""),
        )
        return azure_storage_setting

    def __eq__(self, other):
        if not isinstance(other, AzureStorageSetting):
            return False
        return (
            self.azure_storage_mode == other.azure_storage_mode
            and self.storage_account_name == other.storage_account_name
            and self.blob_container_name == other.blob_container_name
            and self.flow_artifacts_root_path == other.flow_artifacts_root_path
            and self.blob_container_sas_token == other.blob_container_sas_token
            and self.output_datastore_name == other.output_datastore_name
        )

    def __hash__(self):
        return hash(
            (
                self.azure_storage_mode,
                self.storage_account_name,
                self.blob_container_name,
                self.flow_artifacts_root_path,
                self.blob_container_sas_token,
                self.output_datastore_name,
            )
        )

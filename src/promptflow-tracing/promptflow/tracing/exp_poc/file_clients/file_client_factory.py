from .file_client import FileClient
from ..utils.path_utils import PathUtils


class FileClientFactory:

    @staticmethod
    def get_file_client(
        file_identifier: str
    ) -> FileClient:
        if PathUtils.is_data_store_url(file_identifier):
            from .aml_data_store_client import AmlDataStoreClient
            return AmlDataStoreClient(file_identifier)
        if PathUtils.is_blob_storage_url(file_identifier):
            from .azure_blob_client import AzureBlobClient
            return AzureBlobClient(file_identifier)
        else:
            from .local_file_client import LocalFileClient
            return LocalFileClient(file_identifier)

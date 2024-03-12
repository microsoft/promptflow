from .file_client import FileClient
from .azure_blob_client import AzureBlobClient
from .local_file_client import LocalFileClient
from ..utils.path_utils import PathUtils


class FileClientFactory:

    @staticmethod
    def get_file_client(
        file_identifier: str
    ) -> FileClient:
        if PathUtils.is_blob_storage_url(file_identifier):
            return AzureBlobClient(file_identifier)
        else:
            return LocalFileClient(file_identifier)

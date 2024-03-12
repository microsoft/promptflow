from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from .file_client import FileClient
from ..utils.path_utils import PathUtils


class AzureBlobClient(FileClient):
    def __init__(self, url):
        self.__blob_info = PathUtils.parse_blob_url(url)
        self.__client = BlobServiceClient(
            account_url=self.__blob_info.account_url,
            credential=DefaultAzureCredential()
        ).get_container_client(self.__blob_info.container_name)

    def if_file_exist(self) -> bool:
        return self.__client.exists()

    def load(self) -> str:
        blob_data = self.__client.download_blob(self.__blob_info.folder_path).readall()
        return blob_data.decode('utf-8')

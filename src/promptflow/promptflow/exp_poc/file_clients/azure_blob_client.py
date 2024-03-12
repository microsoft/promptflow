from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from .file_client import FileClient
from ..utils.path_utils import PathUtils


class AzureBlobClient(FileClient):
    def __init__(self, blob_url):
        self.blob_url = blob_url
        self.blob_info = PathUtils.parse_blob_url(blob_url)
        self.client = BlobServiceClient(
            account_url=self.blob_info.account_url,
            credential=DefaultAzureCredential()
        ).get_container_client(self.blob_info.container_name)

    def if_file_exist(self) -> bool:
        blob_service_client = BlobServiceClient(self.blob_url, credential=self.credential)
        container_client = blob_service_client.get_container_client(self.blob_url)
        return container_client.exists()

    def load(self) -> str:
        blob_data = self.client.download_blob(self.blob_info.folder_path).readall()
        return blob_data.decode('utf-8')

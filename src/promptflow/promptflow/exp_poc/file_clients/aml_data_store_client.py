import tempfile
import os
from .file_client import FileClient
from ..utils.path_utils import PathUtils
from ..utils.aml_agent import AmlAgent


class AmlDataStoreClient(FileClient):
    def __init__(self, url):
        self.__url = url
        self.__datastore_info = PathUtils.parse_data_store_url(self.__url)
        self.__aml_agent = AmlAgent(self.__datastore_info)

    def if_file_exist(self) -> bool:
        return self.__aml_agent.is_datastore_path_exists(self.__url)

    def load(self) -> str:
        with tempfile.TemporaryDirectory() as temp_folder:
            self.__aml_agent.download_from_datastore_url(
                url=self.__url,
                destination=temp_folder
            )
            file_name = self.__datastore_info.data_path.split('/')[-1]
            local_path = os.path.join(temp_folder, file_name)
            with open(local_path, 'r') as file:
                return file.read()

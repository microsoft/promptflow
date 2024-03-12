from dataclasses import dataclass
import os
import re
from urllib.parse import urlparse


BLOB_URL_REGEX_FORMAT = r"https://([^/]+)\.blob\.core\.windows\.net/.+"


@dataclass
class AzureBlobInfo():
    account_name: str
    account_url: str
    container_name: str
    folder_path: str


class PathUtils:

    @staticmethod
    def is_blob_storage_url(url: str) -> bool:
        match = re.match(
            BLOB_URL_REGEX_FORMAT,
            url
        )
        return match is not None

    @staticmethod
    def parse_blob_url(url: str) -> AzureBlobInfo:
        if not PathUtils.is_blob_storage_url(url):
            raise Exception(f"Invalid blob url: {url}")
        res = urlparse(url)
        dirs = res.path.split('/')
        account_name = re.match(BLOB_URL_REGEX_FORMAT, url)[1]
        account_url = f'{res.scheme}://{res.hostname}'
        container_name = dirs[1]
        if len(dirs) > 2:
            folder_path = os.path.join(*dirs[2:])
        else:
            folder_path = ''

        return AzureBlobInfo(
            account_name=account_name,
            account_url=account_url,
            container_name=container_name,
            folder_path=folder_path
        )

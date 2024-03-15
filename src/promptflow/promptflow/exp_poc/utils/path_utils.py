from dataclasses import dataclass, fields
import os
import re
from urllib.parse import urlparse


BLOB_URL_REGEX_FORMAT = r"https://([^/]+)\.blob\.core\.windows\.net/.+"
LONG_DATASTORE_URI_REGEX_FORMAT = (
    r"subscriptions/([^/]+)/resource[gG]roups/([^/]+)/workspaces/([^/]+)/datastores/([^/]+)/paths/(.+)"
)


@dataclass
class AzureBlobInfo:
    account_name: str
    account_url: str
    container_name: str
    folder_path: str


@dataclass
class HashableDataclass:

    def to_tuple(self):
        data_tuple = tuple(getattr(self, field.name) for field in fields(self))
        return data_tuple


@dataclass
class WorkspaceInfo(HashableDataclass):
    subscription_id: str
    resource_group: str
    workspace_name: str

    def is_valid(self):
        return (
            self.subscription_id
            and self.resource_group
            and self.workspace_name
        )


@dataclass
class DataStoreInfo(WorkspaceInfo):
    datastore_name: str
    data_path: str = None

    def is_valid(self):
        return super().is_valid() and self.datastore_name


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

    @staticmethod
    def is_data_store_url(url: str) -> bool:
        match = re.search(
            LONG_DATASTORE_URI_REGEX_FORMAT,
            url
        )
        return match is not None

    @staticmethod
    def parse_data_store_url(url: str) -> DataStoreInfo:

        match = re.search(
            LONG_DATASTORE_URI_REGEX_FORMAT,
            url
        )
        if not match:
            raise Exception(
                f"Invalid datastore url: {url}"
            )

        datastore_info = DataStoreInfo(
            subscription_id=match.group(1),
            resource_group=match.group(2),
            workspace_name=match.group(3),
            datastore_name=match.group(4),
            data_path=match.group(5)
        )

        return datastore_info

    @staticmethod
    def url_join(url_prefix: str, relative_path: str) -> str:
        return f"{url_prefix.rstrip('/')}/{relative_path.lstrip('/')}"

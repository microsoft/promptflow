import datetime
import logging
import threading
import traceback
from typing import Optional, Tuple

from azure.ai.ml import MLClient
from azure.ai.ml._azure_environments import _get_storage_endpoint_from_metadata
from azure.ai.ml._restclient.v2022_10_01.models import DatastoreType
from azure.ai.ml.constants._common import STORAGE_ACCOUNT_URLS
from azure.ai.ml.entities._datastore.datastore import Datastore
from azure.storage.blob import ContainerClient

from promptflow.exceptions import UserErrorException

datastore_map = {}
client_map = {}
_thread_lock = threading.Lock()
_cache_timeout = 60 * 5  # Will try to refresh default datastore if exceed 5 minutes


def get_client(
    logger: logging.Logger,
    subscription_id: str,
    resource_group_name: str,
    workspace_name: str,
    credential: Optional[object] = None,
) -> Tuple[ContainerClient, str]:
    try:
        # To write data to blob, user should have "Storage Blob Data Contributor" to the storage account.
        if credential is None:
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()

        default_datastore = get_default_datastore(subscription_id, resource_group_name, workspace_name, credential)

        storage_endpoint = _get_storage_endpoint_from_metadata()
        account_url = STORAGE_ACCOUNT_URLS[DatastoreType.AZURE_BLOB].format(
            default_datastore.account_name, storage_endpoint
        )

        from azure.ai.ml.constants._common import LONG_URI_FORMAT

        # Datastore is a notion of AzureML, it is not a notion of Blob Storage.
        # So, we cannot get datastore name by blob client.
        # To generate the azureml uri has datastore name, we need to generate the uri here and pass in to db client.
        return ContainerClient(
            account_url=account_url, container_name=default_datastore.container_name, credential=credential
        ), LONG_URI_FORMAT.format(subscription_id, resource_group_name, workspace_name, default_datastore.name, "")

    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Failed to get blob client: {e}, stack trace is {stack_trace}")
        raise


def get_default_datastore(
    subscription_id: str, resource_group_name: str, workspace_name: str, credential: Optional[object]
) -> Datastore:

    datastore_key = _get_datastore_client_key(subscription_id, resource_group_name, workspace_name)
    datastore = _get_datastore_from_map(datastore_key=datastore_key)
    if datastore is None:
        with _thread_lock:
            datastore = _get_datastore_from_map(datastore_key=datastore_key)
            if datastore is None:
                datastore = _get_default_datastore(subscription_id, resource_group_name, workspace_name, credential)
                datastore_map[datastore_key] = {
                    "expire_at": datetime.datetime.now() + datetime.timedelta(0, _cache_timeout),
                    "datastore": datastore,
                }
    return datastore


def _get_datastore_from_map(datastore_key: str):
    datastore = datastore_map.get(datastore_key, None)
    if datastore is None:
        return None

    if datastore["expire_at"] > datetime.datetime.now():
        return datastore["datastore"]

    return None


def _get_datastore_client_key(subscription_id: str, resource_group_name: str, workspace_name: str) -> str:
    # Azure name allow hyphens and underscores. User @ to avoid possible conflict.
    return f"{subscription_id}@{resource_group_name}@{workspace_name}"


def _get_default_datastore(
    subscription_id: str, resource_group_name: str, workspace_name: str, credential: Optional[object]
) -> Datastore:

    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
    )

    default_datastore = ml_client.datastores.get_default()
    if default_datastore.type != DatastoreType.AZURE_BLOB:
        raise UserErrorException(
            message=f"Default datastore {default_datastore.name} is {default_datastore.type}, not AzureBlob."
        )

    return default_datastore

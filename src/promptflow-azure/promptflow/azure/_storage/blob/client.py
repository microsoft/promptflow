import datetime
import logging
import threading
import traceback
from typing import Callable, Tuple

from azure.ai.ml import MLClient
from azure.ai.ml._azure_environments import _get_storage_endpoint_from_metadata
from azure.ai.ml._restclient.v2022_10_01.models import DatastoreType
from azure.ai.ml.constants._common import LONG_URI_FORMAT, STORAGE_ACCOUNT_URLS
from azure.ai.ml.entities._credentials import AccountKeyConfiguration
from azure.ai.ml.entities._datastore.datastore import Datastore
from azure.ai.ml.operations import DatastoreOperations
from azure.storage.blob import ContainerClient

from promptflow.exceptions import UserErrorException

_datastore_cache = {}
_thread_lock = threading.Lock()
_cache_timeout = 60 * 4  # Align the cache ttl with cosmosdb client.


def get_datastore_container_client(
    logger: logging.Logger,
    subscription_id: str,
    resource_group_name: str,
    workspace_name: str,
    get_credential: Callable,
) -> Tuple[ContainerClient, str]:
    try:
        credential = get_credential()
        datastore_definition, datastore_credential = _get_default_datastore(
            subscription_id, resource_group_name, workspace_name, credential
        )

        storage_endpoint = _get_storage_endpoint_from_metadata()
        account_url = STORAGE_ACCOUNT_URLS[DatastoreType.AZURE_BLOB].format(
            datastore_definition.account_name, storage_endpoint
        )

        # Datastore is a notion of AzureML, it is not a notion of Blob Storage.
        # So, we cannot get datastore name by blob client.
        # To generate the azureml uri has datastore name, we need to generate the uri here and pass in to db client.
        container_client = ContainerClient(
            account_url=account_url, container_name=datastore_definition.container_name, credential=datastore_credential
        )
        blob_base_uri = LONG_URI_FORMAT.format(
            subscription_id, resource_group_name, workspace_name, datastore_definition.name, ""
        )
        if not blob_base_uri.endswith("/"):
            blob_base_uri += "/"

        logger.info(f"Get blob base url for {blob_base_uri}")

        return container_client, blob_base_uri

    except Exception as e:
        stack_trace = traceback.format_exc()
        logger.error(f"Failed to get blob client: {e}, stack trace is {stack_trace}")
        raise


def _get_default_datastore(
    subscription_id: str, resource_group_name: str, workspace_name: str, credential
) -> Tuple[Datastore, str]:

    datastore_key = _get_datastore_client_key(subscription_id, resource_group_name, workspace_name)
    datastore_definition, datastore_credential = _get_datastore_from_cache(datastore_key=datastore_key)
    if datastore_definition is None:
        with _thread_lock:
            datastore_definition, datastore_credential = _get_datastore_from_cache(datastore_key=datastore_key)
            if datastore_definition is None:
                datastore_definition, datastore_credential = _get_aml_default_datastore(
                    subscription_id, resource_group_name, workspace_name, credential
                )
                _datastore_cache[datastore_key] = {
                    "expire_at": datetime.datetime.now() + datetime.timedelta(seconds=_cache_timeout),
                    "datastore_definition": datastore_definition,
                    "datastore_credential": datastore_credential,
                }
    return datastore_definition, datastore_credential


def _get_datastore_from_cache(datastore_key: str) -> Tuple[Datastore, str]:
    datastore = _datastore_cache.get(datastore_key)

    if datastore and datastore["expire_at"] > datetime.datetime.now():
        return datastore["datastore_definition"], datastore["datastore_credential"]

    return None, None


def _get_datastore_client_key(subscription_id: str, resource_group_name: str, workspace_name: str) -> str:
    # Azure name allow hyphens and underscores. User @ to avoid possible conflict.
    return f"{subscription_id}@{resource_group_name}@{workspace_name}"


def _get_aml_default_datastore(
    subscription_id: str, resource_group_name: str, workspace_name: str, credential
) -> Tuple[Datastore, str]:

    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
    )

    default_datastore = ml_client.datastores.get_default(include_secrets=True)
    if default_datastore.type != DatastoreType.AZURE_BLOB:
        raise UserErrorException(
            message=f"Default datastore {default_datastore.name} is {default_datastore.type}, not AzureBlob."
        )

    return default_datastore, _get_datastore_credential(default_datastore, ml_client.datastores)


def _get_datastore_credential(datastore: Datastore, operations: DatastoreOperations):
    # Reference the logic in azure.ai.ml._artifact._artifact_utilities
    # https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ml/azure-ai-ml/azure/ai/ml/_artifacts/_artifact_utilities.py#L103
    credential = datastore.credentials
    if isinstance(credential, AccountKeyConfiguration):
        return credential.account_key
    elif hasattr(credential, "sas_token"):
        return credential.sas_token
    else:
        return operations._credential

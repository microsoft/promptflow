""" download or mount remote data in runtime """
import os
import re
import shutil
from pathlib import Path

import requests

from .error_codes import (
    InvalidAmlDataUri,
    InvalidBlobDataUri,
    InvalidDataUri,
    InvalidWsabsDataUri,
    RuntimeConfigNotProvided,
)
from .runtime_config import RuntimeConfig

SHORT_DATASTORE_URI_REGEX_FORMAT = "azureml://datastores/([^/]+)/paths/(.+)"
LONG_DATASTORE_URI_REGEX_FORMAT = (
    "azureml://subscriptions/([^/]+)/resource[gG]roups/([^/]+)/workspaces/([^/]+)/datastores/([^/]+)/paths/(.+)"
)
JOB_URI_REGEX_FORMAT = "azureml://jobs/([^/]+)/outputs/([^/]+)/paths/(.+)"

DATA_ASSET_ID_REGEX_FORMAT = (
    "azureml://subscriptions/([^/]+)/resource[gG]roups/([^/]+)/workspaces/([^/]+)/data/([^/]+)/versions/(.+)"
)
DATA_ASSET_ID_LABEL_REGEX_FORMAT = (
    "azureml://subscriptions/([^/]+)/resource[gG]roups/([^/]+)/workspaces/([^/]+)/data/([^/]+)/labels/(.+)"
)
ASSET_ARM_ID_REGEX_FORMAT = (
    "azureml:/subscriptions/([^/]+)/resource[gG]roups/([^/]+)/"
    "providers/Microsoft.MachineLearningServices/workspaces/([^/]+)/([^/]+)/([^/]+)/versions/(.+)"
)
AZUREML_VERSION_REGEX_FORMAT = "azureml:([^/]+):(.+)"
AZUREML_LABEL_REGEX_FORMAT = "azureml:([^/]+)@(.+)"


def _get_last_part_of_uri(uri: str) -> str:
    """get last part of uri"""
    return uri.split("/")[-1]


WSABS_REGEX_FORMAT = "wasbs://([^@]+)@([^/]+)/(.+)"


def _wsabs_to_http_url(wsabs_url: str) -> str:
    """convert wsabs url to http url"""
    if not wsabs_url.startswith("wasbs"):
        return wsabs_url

    m = re.match(WSABS_REGEX_FORMAT, wsabs_url)
    if m is None:
        raise InvalidWsabsDataUri(message_format="Invalid wsabs data url: {wsabs_url}", wsabs_url=wsabs_url)

    container, account, path = m.groups()
    return f"https://{account}/{container}/{path}"


BLOB_HTTP_REGEX_FORMAT = "https://([^/]+)/([^/]+)/(.+)"


def _http_to_wsabs_url(url: str) -> str:
    """convert http url to wsabs url"""

    m = re.match(BLOB_HTTP_REGEX_FORMAT, url)
    if m is None:
        raise InvalidBlobDataUri(message_format="Invalid blob data url: {blob_url}", blob_url=url)

    account, container, path = m.groups()
    return f"wasbs://{container}@{account}/{path}"


def _download_blob(uri, destination, credential) -> str:
    uri = _wsabs_to_http_url(uri)
    target_file = _get_last_part_of_uri(uri)
    if destination is not None:
        target_file = os.path.join(destination, target_file)

    from azure.storage.blob import BlobClient

    blob_client = BlobClient.from_blob_url(blob_url=uri, credential=credential)
    with open(target_file, "wb") as my_blob:
        blob_data = blob_client.download_blob()
        blob_data.readinto(my_blob)

    return target_file


def _download_public_http_url(url, destination) -> str:
    target_file = _get_last_part_of_uri(url)
    if destination is not None:
        target_file = os.path.join(destination, target_file)

    with requests.get(url, stream=True) as r:
        with open(target_file, "wb") as f:
            shutil.copyfileobj(r.raw, f)
    return target_file


def _download_aml_uri(uri, destination, credential, runtime_config: RuntimeConfig) -> str:  # noqa: C901
    if not runtime_config and not (uri.startswith("azureml://") or uri.startswith("azureml:/subscriptions/")):
        raise RuntimeConfigNotProvided(message_format="Runtime_config must be provided for short form uri")
    # hide imports not for community version
    from azure.ai.ml import MLClient
    from azure.ai.ml._artifacts._artifact_utilities import download_artifact_from_aml_uri
    from azure.ai.ml.entities import Data

    # asset URI: resolve as datastore uri
    data: Data = None
    if re.match(ASSET_ARM_ID_REGEX_FORMAT, uri):
        sub, rg, ws, _, name, version = re.match(ASSET_ARM_ID_REGEX_FORMAT, uri).groups()
        ml_client = MLClient(credential=credential, subscription_id=sub, resource_group_name=rg, workspace_name=ws)
        data = ml_client.data.get(name, version=version)
    elif re.match(AZUREML_VERSION_REGEX_FORMAT, uri):
        name, version = re.match(AZUREML_VERSION_REGEX_FORMAT, uri).groups()
        ml_client = runtime_config.get_ml_client(credential)
        data = ml_client.data.get(name, version=version)
    elif re.match(AZUREML_LABEL_REGEX_FORMAT, uri):
        name, label = re.match(AZUREML_LABEL_REGEX_FORMAT, uri).groups()
        ml_client = runtime_config.get_ml_client(credential)
        data = ml_client.data.get(name, label=label)
    elif re.match(DATA_ASSET_ID_REGEX_FORMAT, uri):
        # asset URI: long versions
        sub, rg, ws, name, version = re.match(DATA_ASSET_ID_REGEX_FORMAT, uri).groups()
        ml_client = MLClient(credential=credential, subscription_id=sub, resource_group_name=rg, workspace_name=ws)
        data = ml_client.data.get(name, version=version)
    elif re.match(DATA_ASSET_ID_LABEL_REGEX_FORMAT, uri):
        sub, rg, ws, name, label = re.match(DATA_ASSET_ID_LABEL_REGEX_FORMAT, uri).groups()
        ml_client = MLClient(credential=credential, subscription_id=sub, resource_group_name=rg, workspace_name=ws)
        data = ml_client.data.get(name, label=label)

    if data:
        uri = data.path

    # remove trailing slash all the time: it will break download file, and no slash won't break folder
    uri = uri.rstrip("/")
    # we have observed glob like uri including "**/" that will break download;
    # as we remove slash above, only check & remove "**" here.
    if uri.endswith("**"):
        uri = uri[:-2]

    # datastore uri
    if re.match(SHORT_DATASTORE_URI_REGEX_FORMAT, uri):
        ml_client = runtime_config.get_ml_client(credential)
        return download_artifact_from_aml_uri(uri, destination, ml_client.datastores)
    elif re.match(LONG_DATASTORE_URI_REGEX_FORMAT, uri):
        sub, rg, ws, _, _ = re.match(LONG_DATASTORE_URI_REGEX_FORMAT, uri).groups()
        ml_client = MLClient(credential=credential, subscription_id=sub, resource_group_name=rg, workspace_name=ws)
        # download all files in the datastore starts with the url
        return download_artifact_from_aml_uri(uri, destination, ml_client.datastores)
    else:
        raise InvalidAmlDataUri(message_format="Invalid aml data uri: {aml_uri}", aml_uri=uri)


def prepare_data(uri: str, destination: str = None, credential=None, runtime_config: RuntimeConfig = None) -> str:
    """prepare data from blob_uri to local_file.

    Only support download now. TODO: support mount.
    Args:
        uri: uri of the data
        destination: local folder to download or mount data
        credential: credential to access remote storage

    Returns: prepared local path
    """
    # convert to str in case not
    uri = str(uri)
    destination = str(destination)

    Path(destination).mkdir(parents=True, exist_ok=True)

    from .utils._token_utils import get_default_credential

    if uri.startswith("azureml:"):
        if credential is None:
            credential = get_default_credential()
        # asset & datastore uri
        return _download_aml_uri(uri, destination, credential, runtime_config)
    if uri.startswith("wasbs:"):
        # storage blob uri
        if credential is None:
            credential = get_default_credential()
        return _download_blob(uri, destination, credential)
    if uri.startswith("http"):
        # public http url
        return _download_public_http_url(uri, destination)
    if os.path.exists(uri):
        # local file
        return uri
    else:
        raise InvalidDataUri(message_format="Invalid data uri: {uri}", uri=uri)

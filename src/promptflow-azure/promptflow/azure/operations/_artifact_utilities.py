# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

# pylint: disable=protected-access

import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, TypeVar, Union

from azure.ai.ml._artifacts._blob_storage_helper import BlobStorageClient
from azure.ai.ml._artifacts._gen2_storage_helper import Gen2StorageClient
from azure.ai.ml._azure_environments import _get_storage_endpoint_from_metadata
from azure.ai.ml._restclient.v2022_10_01.models import DatastoreType
from azure.ai.ml._scope_dependent_operations import OperationScope
from azure.ai.ml._utils._arm_id_utils import (
    AMLNamedArmId,
    get_resource_name_from_arm_id,
    is_ARM_id_for_resource,
    remove_aml_prefix,
)
from azure.ai.ml._utils._asset_utils import (
    IgnoreFile,
    _build_metadata_dict,
    _validate_path,
    get_ignore_file,
    get_object_hash,
)
from azure.ai.ml._utils._storage_utils import (
    AzureMLDatastorePathUri,
    get_artifact_path_from_storage_url,
    get_storage_client,
)
from azure.ai.ml.constants._common import SHORT_URI_FORMAT, STORAGE_ACCOUNT_URLS
from azure.ai.ml.entities import Environment
from azure.ai.ml.entities._assets._artifacts.artifact import Artifact, ArtifactStorageInfo
from azure.ai.ml.entities._credentials import AccountKeyConfiguration
from azure.ai.ml.entities._datastore._constants import WORKSPACE_BLOB_STORE
from azure.ai.ml.exceptions import ErrorTarget, ValidationException
from azure.ai.ml.operations._datastore_operations import DatastoreOperations
from azure.storage.blob import BlobSasPermissions, generate_blob_sas
from azure.storage.filedatalake import FileSasPermissions, generate_file_sas

from promptflow._utils.logger_utils import LoggerFactory

from ._fileshare_storeage_helper import FlowFileStorageClient

module_logger = LoggerFactory.get_logger(__name__)


def _get_datastore_name(*, datastore_name: Optional[str] = WORKSPACE_BLOB_STORE) -> str:
    datastore_name = WORKSPACE_BLOB_STORE if not datastore_name else datastore_name
    try:
        datastore_name = get_resource_name_from_arm_id(datastore_name)
    except (ValueError, AttributeError, ValidationException):
        module_logger.debug("datastore_name %s is not a full arm id. Proceed with a shortened name.\n", datastore_name)
    datastore_name = remove_aml_prefix(datastore_name)
    if is_ARM_id_for_resource(datastore_name):
        datastore_name = get_resource_name_from_arm_id(datastore_name)
    return datastore_name


def get_datastore_info(operations: DatastoreOperations, name: str) -> Dict[str, str]:
    """Get datastore account, type, and auth information."""
    datastore_info = {}
    if name:
        datastore = operations.get(name, include_secrets=True)
    else:
        datastore = operations.get_default(include_secrets=True)

    storage_endpoint = _get_storage_endpoint_from_metadata()
    credentials = datastore.credentials
    datastore_info["storage_type"] = datastore.type
    datastore_info["storage_account"] = datastore.account_name
    datastore_info["account_url"] = STORAGE_ACCOUNT_URLS[datastore.type].format(
        datastore.account_name, storage_endpoint
    )
    if isinstance(credentials, AccountKeyConfiguration):
        datastore_info["credential"] = credentials.account_key
    else:
        try:
            datastore_info["credential"] = credentials.sas_token
        except Exception as e:  # pylint: disable=broad-except
            if not hasattr(credentials, "sas_token"):
                datastore_info["credential"] = operations._credential
            else:
                raise e

    if datastore.type == DatastoreType.AZURE_BLOB:
        datastore_info["container_name"] = str(datastore.container_name)
    elif datastore.type == DatastoreType.AZURE_DATA_LAKE_GEN2:
        datastore_info["container_name"] = str(datastore.filesystem)
    elif datastore.type == DatastoreType.AZURE_FILE:
        datastore_info["container_name"] = str(datastore.file_share_name)
    else:
        raise Exception(
            f"Datastore type {datastore.type} is not supported for uploads. "
            f"Supported types are {DatastoreType.AZURE_BLOB} and {DatastoreType.AZURE_DATA_LAKE_GEN2}."
        )

    return datastore_info


def list_logs_in_datastore(ds_info: Dict[str, str], prefix: str, legacy_log_folder_name: str) -> Dict[str, str]:
    """Returns a dictionary of file name to blob or data lake uri with SAS token, matching the structure of
    RunDetails.logFiles.

    legacy_log_folder_name: the name of the folder in the datastore that contains the logs
        /azureml-logs/*.txt is the legacy log structure for commandJob and sweepJob
        /logs/azureml/*.txt is the legacy log structure for pipeline parent Job
    """
    if ds_info["storage_type"] not in [
        DatastoreType.AZURE_BLOB,
        DatastoreType.AZURE_DATA_LAKE_GEN2,
    ]:
        raise Exception("Only Blob and Azure DataLake Storage Gen2 datastores are supported.")

    storage_client = get_storage_client(
        credential=ds_info["credential"],
        container_name=ds_info["container_name"],
        storage_account=ds_info["storage_account"],
        storage_type=ds_info["storage_type"],
    )

    items = storage_client.list(starts_with=prefix + "/user_logs/")
    # Append legacy log files if present
    items.extend(storage_client.list(starts_with=prefix + legacy_log_folder_name))

    log_dict = {}
    for item_name in items:
        sub_name = item_name.split(prefix + "/")[1]
        if isinstance(storage_client, BlobStorageClient):
            token = generate_blob_sas(
                account_name=ds_info["storage_account"],
                container_name=ds_info["container_name"],
                blob_name=item_name,
                account_key=ds_info["credential"],
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(minutes=30),
            )
        elif isinstance(storage_client, Gen2StorageClient):
            token = generate_file_sas(  # pylint: disable=no-value-for-parameter
                account_name=ds_info["storage_account"],
                file_system_name=ds_info["container_name"],
                file_name=item_name,
                credential=ds_info["credential"],
                permission=FileSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(minutes=30),
            )

        log_dict[sub_name] = "{}/{}/{}?{}".format(ds_info["account_url"], ds_info["container_name"], item_name, token)
    return log_dict


def _get_default_datastore_info(datastore_operation):
    return get_datastore_info(datastore_operation, None)


def upload_artifact(
    local_path: str,
    datastore_operation: DatastoreOperations,
    operation_scope: OperationScope,
    datastore_name: Optional[str],
    asset_hash: Optional[str] = None,
    show_progress: bool = True,
    asset_name: Optional[str] = None,
    asset_version: Optional[str] = None,
    ignore_file: IgnoreFile = IgnoreFile(None),
    sas_uri=None,
) -> ArtifactStorageInfo:
    """Upload local file or directory to datastore."""
    if sas_uri:
        storage_client = get_storage_client(credential=None, storage_account=None, account_url=sas_uri)
    else:
        datastore_name = _get_datastore_name(datastore_name=datastore_name)
        datastore_info = get_datastore_info(datastore_operation, datastore_name)
        storage_client = FlowFileStorageClient(
            credential=datastore_info["credential"],
            file_share_name=datastore_info["container_name"],
            account_url=datastore_info["account_url"],
            azure_cred=datastore_operation._credential,
        )

    artifact_info = storage_client.upload(
        local_path,
        asset_hash=asset_hash,
        show_progress=show_progress,
        name=asset_name,
        version=asset_version,
        ignore_file=ignore_file,
    )
    artifact_info["remote path"] = os.path.join(
        storage_client.directory_client.directory_path, artifact_info["remote path"]
    )
    return artifact_info


def download_artifact(
    starts_with: Union[str, os.PathLike],
    destination: str,
    datastore_operation: DatastoreOperations,
    datastore_name: Optional[str],
    datastore_info: Optional[Dict] = None,
) -> str:
    """Download datastore path to local file or directory.

    :param Union[str, os.PathLike] starts_with: Prefix of blobs to download
    :param str destination: Path that files will be written to
    :param DatastoreOperations datastore_operation: Datastore operations
    :param Optional[str] datastore_name: name of datastore
    :param Dict datastore_info: the return value of invoking get_datastore_info
    :return str: Path that files were written to
    """
    starts_with = starts_with.as_posix() if isinstance(starts_with, Path) else starts_with
    datastore_name = _get_datastore_name(datastore_name=datastore_name)
    if datastore_info is None:
        datastore_info = get_datastore_info(datastore_operation, datastore_name)
    storage_client = get_storage_client(**datastore_info)
    storage_client.download(starts_with=starts_with, destination=destination)
    return destination


def download_artifact_from_storage_url(
    blob_url: str,
    destination: str,
    datastore_operation: DatastoreOperations,
    datastore_name: Optional[str],
) -> str:
    """Download datastore blob URL to local file or directory."""
    datastore_name = _get_datastore_name(datastore_name=datastore_name)
    datastore_info = get_datastore_info(datastore_operation, datastore_name)
    starts_with = get_artifact_path_from_storage_url(
        blob_url=str(blob_url), container_name=datastore_info.get("container_name")
    )
    return download_artifact(
        starts_with=starts_with,
        destination=destination,
        datastore_operation=datastore_operation,
        datastore_name=datastore_name,
        datastore_info=datastore_info,
    )


def download_artifact_from_aml_uri(uri: str, destination: str, datastore_operation: DatastoreOperations):
    """Downloads artifact pointed to by URI of the form `azureml://...` to destination.

    :param str uri: AzureML uri of artifact to download
    :param str destination: Path to download artifact to
    :param DatastoreOperations datastore_operation: datastore operations
    :return str: Path that files were downloaded to
    """
    parsed_uri = AzureMLDatastorePathUri(uri)
    return download_artifact(
        starts_with=parsed_uri.path,
        destination=destination,
        datastore_operation=datastore_operation,
        datastore_name=parsed_uri.datastore,
    )


def aml_datastore_path_exists(
    uri: str, datastore_operation: DatastoreOperations, datastore_info: Optional[dict] = None
):
    """Checks whether `uri` of the form "azureml://" points to either a directory or a file.

    :param str uri: azure ml datastore uri
    :param DatastoreOperations datastore_operation: Datastore operation
    :param dict datastore_info: return value of get_datastore_info
    """
    parsed_uri = AzureMLDatastorePathUri(uri)
    datastore_info = datastore_info or get_datastore_info(datastore_operation, parsed_uri.datastore)
    return get_storage_client(**datastore_info).exists(parsed_uri.path)


def _upload_to_datastore(
    operation_scope: OperationScope,
    datastore_operation: DatastoreOperations,
    path: Union[str, Path, os.PathLike],
    artifact_type: str,
    datastore_name: Optional[str] = None,
    show_progress: bool = True,
    asset_name: Optional[str] = None,
    asset_version: Optional[str] = None,
    asset_hash: Optional[str] = None,
    ignore_file: Optional[IgnoreFile] = None,
    sas_uri: Optional[str] = None,  # contains registry sas url
) -> ArtifactStorageInfo:
    _validate_path(path, _type=artifact_type)
    if not ignore_file:
        ignore_file = get_ignore_file(path)
    if not asset_hash:
        asset_hash = get_object_hash(path, ignore_file)
    artifact = upload_artifact(
        str(path),
        datastore_operation,
        operation_scope,
        datastore_name,
        show_progress=show_progress,
        asset_hash=asset_hash,
        asset_name=asset_name,
        asset_version=asset_version,
        ignore_file=ignore_file,
        sas_uri=sas_uri,
    )
    return artifact


def _upload_and_generate_remote_uri(
    operation_scope: OperationScope,
    datastore_operation: DatastoreOperations,
    path: Union[str, Path, os.PathLike],
    artifact_type: str = ErrorTarget.ARTIFACT,
    datastore_name: str = WORKSPACE_BLOB_STORE,
    show_progress: bool = True,
) -> str:
    # Asset name is required for uploading to a datastore
    asset_name = str(uuid.uuid4())
    artifact_info = _upload_to_datastore(
        operation_scope=operation_scope,
        datastore_operation=datastore_operation,
        path=path,
        datastore_name=datastore_name,
        asset_name=asset_name,
        artifact_type=artifact_type,
        show_progress=show_progress,
    )

    path = artifact_info.relative_path
    datastore = AMLNamedArmId(artifact_info.datastore_arm_id).asset_name
    return SHORT_URI_FORMAT.format(datastore, path)


def _update_metadata(name, version, indicator_file, datastore_info) -> None:
    storage_client = get_storage_client(**datastore_info)

    if isinstance(storage_client, BlobStorageClient):
        _update_blob_metadata(name, version, indicator_file, storage_client)
    elif isinstance(storage_client, Gen2StorageClient):
        _update_gen2_metadata(name, version, indicator_file, storage_client)


def _update_blob_metadata(name, version, indicator_file, storage_client) -> None:
    container_client = storage_client.container_client
    if indicator_file.startswith(storage_client.container):
        indicator_file = indicator_file.split(storage_client.container)[1]
    blob = container_client.get_blob_client(blob=indicator_file)
    blob.set_blob_metadata(_build_metadata_dict(name=name, version=version))


def _update_gen2_metadata(name, version, indicator_file, storage_client) -> None:
    artifact_directory_client = storage_client.file_system_client.get_directory_client(indicator_file)
    artifact_directory_client.set_metadata(_build_metadata_dict(name=name, version=version))


T = TypeVar("T", bound=Artifact)


def _check_and_upload_path(
    artifact: T,
    asset_operations: Union["DataOperations", "ModelOperations", "CodeOperations", "FeatureSetOperations"],
    artifact_type: str,
    datastore_name: Optional[str] = None,
    sas_uri: Optional[str] = None,
    show_progress: bool = True,
):
    """Checks whether `artifact` is a path or a uri and uploads it to the datastore if necessary.
    param T artifact: artifact to check and upload param
    Union["DataOperations", "ModelOperations", "CodeOperations"]
    asset_operations:     the asset operations to use for uploading
    param str datastore_name: the name of the datastore to upload to
    param str sas_uri: the sas uri to use for uploading
    """
    from azure.ai.ml._utils.utils import is_mlflow_uri, is_url

    datastore_name = artifact.datastore
    if (
        hasattr(artifact, "local_path")
        and artifact.local_path is not None
        or (
            hasattr(artifact, "path")
            and artifact.path is not None
            and not (is_url(artifact.path) or is_mlflow_uri(artifact.path))
        )
    ):
        path = (
            Path(artifact.path)
            if hasattr(artifact, "path") and artifact.path is not None
            else Path(artifact.local_path)
        )
        if not path.is_absolute():
            path = Path(artifact.base_path, path).resolve()
        uploaded_artifact = _upload_to_datastore(
            asset_operations._operation_scope,
            asset_operations._datastore_operation,
            path,
            datastore_name=datastore_name,
            asset_name=artifact.name,
            asset_version=str(artifact.version),
            asset_hash=artifact._upload_hash if hasattr(artifact, "_upload_hash") else None,
            sas_uri=sas_uri,
            artifact_type=artifact_type,
            show_progress=show_progress,
            ignore_file=getattr(artifact, "_ignore_file", None),
        )
    return uploaded_artifact


def _check_and_upload_env_build_context(
    environment: Environment,
    operations: "EnvironmentOperations",
    sas_uri=None,
    show_progress: bool = True,
) -> Environment:
    if environment.path:
        uploaded_artifact = _upload_to_datastore(
            operations._operation_scope,
            operations._datastore_operation,
            environment.path,
            asset_name=environment.name,
            asset_version=str(environment.version),
            asset_hash=environment._upload_hash,
            sas_uri=sas_uri,
            artifact_type=ErrorTarget.ENVIRONMENT,
            datastore_name=environment.datastore,
            show_progress=show_progress,
        )
        # TODO: Depending on decision trailing "/" needs to stay or not. EMS requires it to be present
        environment.build.path = uploaded_artifact.full_storage_path + "/"
    return environment

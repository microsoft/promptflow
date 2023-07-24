from pathlib import Path

from azure.ai.ml import MLClient
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import Data
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.identity import AzureCliCredential, DefaultAzureCredential


def get_or_create_data(ml_client: MLClient, data_name, data_file):
    try:
        data = ml_client.data.get(data_name, label="latest")
    except Exception:
        data = Data(name=data_name, path=data_file, type=AssetTypes.URI_FILE)
        data = ml_client.data.create_or_update(data)
    return data


def get_cred():
    """get credential for azure storage"""
    # resolve requests
    try:
        credential = AzureCliCredential()
        token = credential.get_token("https://management.azure.com/.default")
    except Exception:
        credential = DefaultAzureCredential()
        # ensure we can get token
        token = credential.get_token("https://management.azure.com/.default")

    assert token is not None
    return credential


def get_azure_blob_service_client(storage_account_name, container_name, credential=None) -> ContainerClient:
    """Initialize blob service client"""

    if credential is None:
        credential = get_cred()

    blob_account_url = f"https://{storage_account_name}.blob.core.windows.net"
    blob_service_client = BlobServiceClient(blob_account_url, credential=credential)

    # create container if not existed
    container = blob_service_client.get_container_client(container_name)
    if not container.exists():
        blob_service_client.create_container(container_name)

    return container


def upload_data(local_file: Path, container_client: ContainerClient) -> str:
    """upload data to azure blob

    Returns:
        blob url
    """
    local_file_name = local_file.name
    blob_client = container_client.get_blob_client(local_file_name)
    if blob_client.exists():
        return blob_client.url

    print("\nUploading to Azure Storage as blob: " + blob_client.url)

    # Upload the created file
    with open(file=local_file, mode="rb") as data:
        blob_client.upload_blob(data)

    return blob_client.url

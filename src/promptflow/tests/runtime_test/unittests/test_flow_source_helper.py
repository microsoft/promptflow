import io
import os
import sys
import tarfile
import uuid
import zipfile
from datetime import datetime, timedelta

import pytest
import requests
from azure.ai.ml import MLClient
from azure.storage.fileshare._shared.models import AccountSasPermissions, ResourceTypes
from azure.storage.fileshare._shared_access_signature import generate_account_sas

from promptflow._constants import ComputeType
from promptflow.contracts.runtime import AzureFileShareInfo
from promptflow.runtime.runtime_config import RuntimeConfig
from promptflow.runtime.utils._utils import get_logger, get_workspace_config

from .._utils import get_runtime_config

logger = get_logger(__name__, std_out=True)
LINUX_DOWNLOAD = "https://azcopyvnext.azureedge.net/release20230530/azcopy_linux_amd64_10.19.0.tar.gz"
WINDOWS_DOWNLOAD = "https://azcopyvnext.azureedge.net/release20230530/azcopy_windows_amd64_10.19.0.zip"


def find(name, path):
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(root, name)


@pytest.fixture
def azcopy():
    logger.info("Downloading azcopy in platform %s", sys.platform)
    if sys.platform == "linux":
        r = requests.get(LINUX_DOWNLOAD)
        with open("azcopy.tar.gz", "wb") as f:
            f.write(r.content)
        tar = tarfile.open("azcopy.tar.gz")
        tar.extractall(os.getcwd())
        tar.close()
    else:
        r = requests.get(WINDOWS_DOWNLOAD)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(os.getcwd())

    azcopy_exe = "azcopy" if sys.platform == "linux" else "azcopy.exe"
    azcopy_path = find(azcopy_exe, os.getcwd())
    os.environ["AZCOPY_EXECUTABLE"] = azcopy_path
    yield azcopy_path


@pytest.fixture
def aml_runtime_config(ml_client: MLClient):
    config = get_workspace_config(ml_client=ml_client, logger=logger)

    runtime_config = get_runtime_config(
        args=[
            "deployment.edition=enterprise",
            f'deployment.mt_service_endpoint={config["mt_service_endpoint"]}',
            f'deployment.subscription_id={config["subscription_id"]}',
            f'deployment.resource_group={config["resource_group"]}',
            f'deployment.workspace_name={config["workspace_name"]}',
            f'deployment.workspace_id={config["workspace_id"]}',
            f'storage.storage_account={config["storage_account"]}',
        ]
    )
    yield runtime_config


@pytest.fixture
def file_account_sas(ml_client: MLClient, aml_runtime_config: RuntimeConfig):

    keys = ml_client.workspaces.get_keys()
    storage_key = keys.user_storage_key

    account_sas = generate_account_sas(
        account_name=aml_runtime_config.storage.storage_account,
        account_key=storage_key,
        resource_types=ResourceTypes(container=True, object=True),
        permission=AccountSasPermissions(read=True, list=True),
        expiry=datetime.utcnow() + timedelta(days=1),
    )
    yield account_sas


@pytest.mark.unittest
def test_download_azurefileshare(azcopy: str, file_account_sas: str):
    logger.info("azcopy path: %s", azcopy)

    sas_url = (
        "https://promptfloweast4063704120.file.core.windows.net/"
        "code-391ff5ac-6576-460f-ba4d-7e03433c68b6/Users/ci_test/*?%s"
    )
    sas_url = sas_url % file_account_sas
    run_id = str(uuid.uuid4())

    import promptflow.runtime.utils._flow_source_helper as _flow_source_helper

    _flow_source_helper.AZCOPY_EXE = azcopy
    logger.info("Download files to requests/%s", run_id)
    _flow_source_helper.fill_working_dir(
        compute_type=ComputeType.MANAGED_ONLINE_DEPLOYMENT,
        flow_source_info=AzureFileShareInfo(working_dir="Users/ci_test/", sas_url=sas_url),
        run_id=run_id,
    )

    assert os.path.exists(
        os.path.join("requests", run_id, "test.txt")
    ), "Download azurefileshare failed. Cannot find test.txt"


@pytest.mark.unittest
def test_download_azurefileshare_not_found(azcopy: str, file_account_sas: str):
    logger.info("azcopy path: %s", azcopy)

    sas_url = (
        "https://promptfloweast4063704120.file.core.windows.net/"
        "code-391ff5ac-6576-460f-ba4d-7e03433c68b6/Users/not_found/*?%s"
    )
    sas_url = sas_url % file_account_sas
    run_id = str(uuid.uuid4())

    import promptflow.runtime.utils._flow_source_helper as _flow_source_helper

    _flow_source_helper.AZCOPY_EXE = azcopy
    with pytest.raises(_flow_source_helper.AzureFileShareNotFoundError):
        _flow_source_helper.fill_working_dir(
            compute_type=ComputeType.MANAGED_ONLINE_DEPLOYMENT,
            flow_source_info=AzureFileShareInfo(working_dir="Users/not_found/", sas_url=sas_url),
            run_id=run_id,
        )

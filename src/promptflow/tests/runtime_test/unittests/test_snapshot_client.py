import json
import os
import uuid
from pathlib import Path

import pytest
import requests
from azure.ai.ml import MLClient

from promptflow.runtime.error_codes import SnapshotNotFound
from promptflow.runtime.runtime_config import RuntimeConfig
from promptflow.runtime.utils._token_utils import MANAGEMENT_OAUTH_SCOPE
from promptflow.runtime.utils._utils import get_logger, get_workspace_config

from .._utils import get_runtime_config

logger = get_logger(__name__)


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


def create_snapshot(runtime_config: RuntimeConfig):
    create_uri = (
        "{endpoint}/content/v2.0/subscriptions/{sub}/resourceGroups/{rg}/"
        "providers/Microsoft.MachineLearningServices/workspaces/{ws}/snapshots/uri"
    )
    body = {
        "Uri": "https://promptfloweast4063704120.blob.core.windows.net/testdata/test_snapshot/",
        "Name": "name",
        "Version": "1",
    }
    from .._azure_utils import get_cred

    credential = get_cred()
    token = credential.get_token(MANAGEMENT_OAUTH_SCOPE)
    headers = {"Authorization": "Bearer %s" % (token.token)}
    response = requests.put(
        create_uri.format(
            endpoint=runtime_config.deployment.mt_service_endpoint,
            sub=runtime_config.deployment.subscription_id,
            rg=runtime_config.deployment.resource_group,
            ws=runtime_config.deployment.workspace_name,
        ),
        json=body,
        headers=headers,
    )
    assert response.status_code == 200, "Cannot create a new snapshot"
    data = json.loads(response.content)
    return data["item1"]["id"]


@pytest.mark.unittest
def test_download_snapshot(aml_runtime_config: RuntimeConfig):
    new_snapshot_id = create_snapshot(aml_runtime_config)
    snapshot_client = aml_runtime_config.get_snapshot_client()
    download_path = f"./{uuid.uuid4()}"
    os.makedirs(download_path, exist_ok=True)
    snapshot_client.download_snapshot(new_snapshot_id, Path(download_path))

    assert os.path.exists(os.path.join(download_path, "test.txt"))


@pytest.mark.unittest
def test_download_snapshot_not_found(aml_runtime_config: RuntimeConfig):
    snapshot_client = aml_runtime_config.get_snapshot_client()
    with pytest.raises(SnapshotNotFound):
        snapshot_client.download_snapshot(uuid.uuid4(), Path("./snapshots"))

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from azure.ai.ml import MLClient

from promptflow.contracts.run_info import FlowRunInfo, Status
from promptflow.contracts.runtime import (
    AzureFileShareInfo,
    BulkRunRequestV2,
    FlowRequestV2,
    FlowSource,
    FlowSourceType,
    SnapshotInfo,
)
from promptflow.exceptions import FlowRunTimeoutError
from promptflow.runtime.runtime import (
    execute_bulk_run_request,
    execute_flow_request,
    execute_flow_request_multiprocessing,
)
from promptflow.runtime.runtime_config import RuntimeConfig, load_runtime_config
from promptflow.runtime.utils._token_utils import MANAGEMENT_OAUTH_SCOPE
from promptflow.runtime.utils._utils import get_logger, get_workspace_config

from .._utils import get_runtime_config

logger = get_logger(__name__)


def execute_sleep(x, y):
    time.sleep(120)


def init_flow_run(runtime_config: RuntimeConfig, flow_id: str, run_id: str, status: Status):
    storage = runtime_config.get_run_storage()
    flow_run_info = FlowRunInfo(
        run_id=run_id,
        status=status,
        error=None,
        inputs=None,
        output=None,
        metrics=None,
        request=None,
        parent_run_id=run_id,
        root_run_id=run_id,
        source_run_id=None,
        flow_id=flow_id,
        start_time=datetime.utcnow(),
        end_time=None,
        index=None,
    )
    storage.persist_flow_run(flow_run_info)


def get_run_status(runtime_config: RuntimeConfig, run_id: str):
    storage = runtime_config.get_run_storage()
    return storage.get_run_status(run_id)


def crete_flow_request_v2():
    flow_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    flow_source = FlowSource(
        flow_source_type=FlowSourceType.AzureFileShare,
        flow_source_info=AzureFileShareInfo(
            working_dir=Path(__file__).parent.parent.parent.absolute() / "test_configs" / "flows" / "simple_fetch_url"
        ),
        flow_dag_file="flow.dag.yaml",
    )
    connections = {}
    request = FlowRequestV2(
        flow_id=flow_id,
        flow_run_id=run_id,
        flow_source=flow_source,
        connections=connections,
        inputs={"url": "https://www.bing.com"},
    )
    return request


def crete_bulkrun_request_v2(snapshot_id):
    flow_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    flow_source = FlowSource(
        flow_source_type=FlowSourceType.Snapshot,
        flow_source_info=SnapshotInfo(snapshot_id=snapshot_id),
        flow_dag_file="flow.dag.yaml",
    )
    connections = {}
    data_uri = (
        "azureml://subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourcegroups/promptflow"
        "/workspaces/promptflow-eastus/datastores/workspaceblobstore/paths/UI/2023-07-10_030021_UTC/url.csv"
    )
    request = BulkRunRequestV2(
        flow_id=flow_id,
        flow_run_id=run_id,
        flow_source=flow_source,
        connections=connections,
        inputs_mapping={"url": "${data.url}"},
        data_inputs={"data": data_uri},
    )
    return request


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
        "Uri": "https://promptfloweast4063704120.blob.core.windows.net/testdata/test_bulkrun/",
        "Name": "test_bulkrun",
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


@pytest.fixture
def runtime_config() -> RuntimeConfig:
    return load_runtime_config()


@pytest.mark.unittest
def test_flow_request_v2(runtime_config: RuntimeConfig):
    request = crete_flow_request_v2()
    result = execute_flow_request_multiprocessing(runtime_config, request, execute_flow_request)
    assert result is not None and len(result) > 0
    assert result["flow_runs"][0]["status"] == "Completed"


@patch("promptflow.runtime.runtime.SYNC_SUBMISSION_TIMEOUT", 1)
@patch("promptflow.runtime.runtime.WAIT_SUBPROCESS_EXCEPTION_TIMEOUT", 1)
@pytest.mark.unittest
def test_flow_request_v2_timeout(runtime_config: RuntimeConfig):
    request = crete_flow_request_v2()
    beg = time.time()
    with pytest.raises(FlowRunTimeoutError):
        execute_flow_request_multiprocessing(runtime_config, request, execute_sleep)
    end = time.time()
    assert end - beg < 10


@pytest.mark.unittest
def test_bulkrun_request_v2(aml_runtime_config: RuntimeConfig):
    snapshot_id = create_snapshot(aml_runtime_config)
    request = crete_bulkrun_request_v2(snapshot_id)
    init_flow_run(aml_runtime_config, request.flow_id, request.flow_run_id, Status.NotStarted)
    result = execute_flow_request_multiprocessing(aml_runtime_config, request, execute_bulk_run_request)
    assert result is not None and len(result) > 0
    assert result["flow_runs"][0]["status"] == "Completed"


@patch("promptflow.runtime.runtime.STATUS_CHECKER_INTERVAL", 1)
@pytest.mark.unittest
def test_cancel_flow_v2(runtime_config: RuntimeConfig):
    flow_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    flow_source = None
    connections = {}
    request = BulkRunRequestV2(flow_id=flow_id, flow_run_id=run_id, flow_source=flow_source, connections=connections)
    init_flow_run(runtime_config, flow_id, run_id, Status.CancelRequested)

    execute_flow_request_multiprocessing(runtime_config, request, execute_sleep)

    status = get_run_status(runtime_config, run_id)
    assert status == Status.Canceled.value

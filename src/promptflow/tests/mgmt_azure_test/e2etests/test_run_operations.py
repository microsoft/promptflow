# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from azure.ai.ml import MLClient
from azure.identity import AzureCliCredential, DefaultAzureCredential

import promptflow.azure as pf
from promptflow.azure import PFClient, configure
from promptflow.sdk._constants import PORTAL_URL_KEY
from promptflow.sdk._load_functions import load_run
from promptflow.sdk.entities import Run
from promptflow.utils.utils import is_in_ci_pipeline

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
MODEL_ROOT = TEST_ROOT / "test_configs/e2e_samples"
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
FLOWS_DIR = "./tests/test_configs/flows"


@pytest.fixture(scope="session")
def remote_client() -> PFClient:
    cred = DefaultAzureCredential()
    if is_in_ci_pipeline():
        cred = AzureCliCredential()
    client = MLClient(
        credential=cred,
        subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
        resource_group_name="promptflow",
        workspace_name="promptflow-eastus",
    )
    configure(client=client)
    return PFClient(client)


@pytest.fixture
def runtime():
    return "demo-mir"


# TODO(2528577): we should run these test with recording mode.
@pytest.mark.e2etest
class TestFlowRun:
    def test_run_bulk(self, remote_client, runtime):
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{FLOWS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        assert isinstance(run, Run)

    def test_run_bulk_from_yaml(self, remote_client, runtime):
        run_id = str(uuid.uuid4())
        run = load_run(
            source=f"{FLOWS_DIR}/runs/sample_bulk_run_cloud.yaml",
            params_override=[{"name": run_id, "runtime": runtime}],
        )
        run = remote_client.runs.create_or_update(run=run)
        assert isinstance(run, Run)

    def test_basic_evaluation(self, remote_client, runtime):
        data_path = f"{FLOWS_DIR}/webClassification3.jsonl"

        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        assert isinstance(run, Run)
        remote_client.runs.stream(run=run.name)

        run = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            data=data_path,
            run=run,
            column_mapping={"groundtruth": "${data.answer}", "prediction": "${run.outputs.category}"},
            runtime=runtime,
        )
        assert isinstance(run, Run)
        remote_client.runs.stream(run=run.name)

    def test_run_with_env_overwrite(self, remote_client, runtime):
        run = load_run(
            source=f"{FLOWS_DIR}/runs/run_with_env.yaml",
            params_override=[{"runtime": runtime}],
        )
        run = remote_client.runs.create_or_update(run=run)
        assert isinstance(run, Run)

    def test_list_runs(self, remote_client):
        runs = remote_client.runs.list(max_results=10)
        for run in runs:
            print(json.dumps(run._to_dict(), indent=4))
        assert len(runs) == 10

    def test_show_run(self, remote_client):
        run = remote_client.runs.get(run="4cf2d5e9-c78f-4ab8-a3ee-57675f92fb74")
        run_dict = run._to_dict()
        print(json.dumps(run_dict, indent=4))
        assert run_dict[PORTAL_URL_KEY]

    def test_show_run_details(self, remote_client):
        details = remote_client.runs.get_details(
            run="4cf2d5e9-c78f-4ab8-a3ee-57675f92fb74",
        )
        assert details.shape[0] == 40

    def test_show_metrics(self, remote_client):
        metrics = remote_client.runs.get_metrics(
            run="4cf2d5e9-c78f-4ab8-a3ee-57675f92fb74",
        )
        print(json.dumps(metrics, indent=4))
        assert metrics

    def test_stream_run_logs(self, remote_client, capfd):
        remote_client.runs.stream(run="4cf2d5e9-c78f-4ab8-a3ee-57675f92fb74")
        out, err = capfd.readouterr()
        print(out)
        assert 'Run status: "Completed"' in out

    def test_stream_failed_run_logs(self, remote_client, capfd):
        remote_client.runs.stream(run="3dfd077a-f071-443e-9c4e-d41531710950")
        out, err = capfd.readouterr()
        print(out)
        assert 'Run status: "Failed"' in out
        assert "Error:{" in out

    def test_visualize(self) -> None:
        # configure client
        ml_client = MLClient(
            credential=AzureCliCredential() if is_in_ci_pipeline() else DefaultAzureCredential(),
            subscription_id="96aede12-2f73-41cb-b983-6d11a904839b",
            resource_group_name="promptflow",
            workspace_name="promptflow-canary-dev",
        )
        pf_client = PFClient(ml_client)

        names = [
            "de5eb4f9-d561-48f1-a91b-f301af72285f",
            "de5eb4f9-d561-48f1-a91b-f301af72285f_594cd6ac-e8f3-4edc-944b-a2774467bd23_variant_1",
            "de5eb4f9-d561-48f1-a91b-f301af72285f_594cd6ac-e8f3-4edc-944b-a2774467bd23_variant_2",
            "471baf09-ec4d-4075-9039-8e487750dbe6",
            "6d3dd598-b824-45cd-8c64-d34789e65264",
        ]
        pf_client.runs.visualize(names=names)

    def test_run_bulk_without_retry(self, remote_client):
        from azure.core.pipeline.transport._requests_basic import RequestsTransport
        from azure.core.rest._requests_basic import RestRequestsTransportResponse
        from requests import Response

        from promptflow.azure._restclient.flow.models import SubmitBulkRunRequest
        from promptflow.azure._restclient.flow_service_caller import FlowRequestException
        from promptflow.azure.operations import RunOperations

        mock_run = MagicMock()
        mock_run._runtime = "fake_runtime"
        mock_run._to_rest_object.return_value = SubmitBulkRunRequest()
        with patch.object(RunOperations, "_resolve_data_to_asset_id"), patch.object(RunOperations, "_resolve_flow"):
            with patch.object(RequestsTransport, "send") as mock_request:
                fake_response = Response()
                fake_response.status_code = 500
                fake_response._content = b'{"error": "error"}'
                fake_response._content_consumed = True
                mock_request.return_value = RestRequestsTransportResponse(
                    request=None,
                    internal_response=fake_response,
                )
                with pytest.raises(FlowRequestException):
                    remote_client.runs.create_or_update(run=mock_run)
                assert mock_request.call_count == 1

    def test_run_data_not_provided(self):
        with pytest.raises(ValueError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
            )
        assert "at least one of data or run must be provided" in str(e)

    def test_run_without_dump(self, remote_client: PFClient, runtime: str) -> None:
        from promptflow.sdk._orm.run_info import RunInfo
        from promptflow.sdk.exceptions import RunNotFoundError

        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{FLOWS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        # cloud run should not dump to database
        with pytest.raises(RunNotFoundError):
            RunInfo.get(run.name)

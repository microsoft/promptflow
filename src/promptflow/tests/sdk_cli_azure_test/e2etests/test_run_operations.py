# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from promptflow._sdk._load_functions import load_run
from promptflow._sdk.entities import Run
from promptflow.azure import PFClient
from promptflow.azure.operations import RunOperations

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
MODEL_ROOT = TEST_ROOT / "test_configs/e2e_samples"
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
FLOWS_DIR = "./tests/test_configs/flows"
RUNS_DIR = "./tests/test_configs/runs"
DATAS_DIR = "./tests/test_configs/datas"


# TODO(2528577): we should run these test with recording mode.
@pytest.mark.e2etest
class TestFlowRun:
    def test_run_bulk(self, remote_client, pf, runtime):
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        assert isinstance(run, Run)

    def test_run_bulk_from_yaml(self, remote_client, pf, runtime):
        run_id = str(uuid.uuid4())
        run = load_run(
            source=f"{RUNS_DIR}/sample_bulk_run_cloud.yaml",
            params_override=[{"name": run_id, "runtime": runtime}],
        )
        run = remote_client.runs.create_or_update(run=run)
        assert isinstance(run, Run)

    def test_basic_evaluation(self, remote_client, pf, runtime):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        assert isinstance(run, Run)
        remote_client.runs.stream(run=run.name)

        eval_run = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            data=data_path,
            run=run,
            column_mapping={
                "groundtruth": "${data.answer}",
                "prediction": "${run.outputs.category}",
            },
            runtime=runtime,
        )
        assert isinstance(eval_run, Run)
        remote_client.runs.stream(run=eval_run.name)

        # evaluation run without data
        eval_run = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            run=run,
            column_mapping={
                # evaluation reference run.inputs
                "groundtruth": "${run.inputs.url}",
                "prediction": "${run.outputs.category}",
            },
            runtime=runtime,
        )
        assert isinstance(eval_run, Run)
        remote_client.runs.stream(run=eval_run.name)

    def test_run_with_connection_overwrite(self, remote_client, pf, runtime):
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            connections={"classify_with_llm": {"connection": "azure_open_ai"}},
            runtime=runtime,
        )
        assert isinstance(run, Run)

    def test_run_with_env_overwrite(self, remote_client, pf, runtime):
        run = load_run(
            source=f"{RUNS_DIR}/run_with_env.yaml",
            params_override=[{"runtime": runtime}],
        )
        run = remote_client.runs.create_or_update(run=run)
        assert isinstance(run, Run)

    def test_run_with_remote_data(
        self, remote_client, pf, runtime, remote_web_classification_data
    ):
        # run with arm id
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"azureml:{remote_web_classification_data.id}",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        assert isinstance(run, Run)
        # run with name version
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"azureml:{remote_web_classification_data.name}:{remote_web_classification_data.version}",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        assert isinstance(run, Run)

    def test_run_bulk_not_exist(self, pf, runtime):
        test_data = f"{DATAS_DIR}/webClassification1.jsonl"
        with pytest.raises(FileNotFoundError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
                # data with file:/// prefix is not supported, should raise not exist error
                data=f"file:///{Path(test_data).resolve().absolute()}",
                column_mapping={"url": "${data.url}"},
                variant="${summarize_text_content.variant_0}",
                runtime=runtime,
            )
        assert "does not exist" in str(e.value)

    def test_list_runs(self, remote_client):
        runs = remote_client.runs.list(max_results=10)
        for run in runs:
            print(json.dumps(run._to_dict(), indent=4))
        assert len(runs) == 10

    def test_show_run(self, remote_client):
        run = remote_client.runs.get(
            run="classification_accuracy_eval_default_20230808_153241_422491"
        )
        run_dict = run._to_dict()
        print(json.dumps(run_dict, indent=4))
        assert run_dict == {
            "name": "classification_accuracy_eval_default_20230808_153241_422491",
            "created_on": "2023-08-08T07:32:52.761030+00:00",
            "status": "Completed",
            "display_name": "classification_accuracy_eval_default_20230808_153241_422491",
            "description": None,
            "tags": {},
            "properties": {
                "azureml.promptflow.runtime_name": "demo-mir",
                "azureml.promptflow.runtime_version": "20230801.v1",
                "azureml.promptflow.definition_file_name": "flow.dag.yaml",
                "azureml.promptflow.inputs_mapping": '{"groundtruth":"${data.answer}","prediction":"${run.outputs.category}"}',  # noqa: E501
                "azureml.promptflow.snapshot_id": "e5d50c43-7ad2-4354-9ce4-4f56f0ea9a30",
                "azureml.promptflow.total_tokens": "0",
            },
            "creation_context": {
                "userObjectId": "c05e0746-e125-4cb3-9213-a8b535eacd79",
                "userPuId": "10032000324F7449",
                "userIdp": None,
                "userAltSecId": None,
                "userIss": "https://sts.windows.net/72f988bf-86f1-41af-91ab-2d7cd011db47/",
                "userTenantId": "72f988bf-86f1-41af-91ab-2d7cd011db47",
                "userName": "Honglin Du",
                "upn": None,
            },
            "start_time": "2023-08-08T07:32:56.637761+00:00",
            "end_time": "2023-08-08T07:33:07.853922+00:00",
            "duration": "00:00:11.2161606",
            "portal_url": "https://ml.azure.com/prompts/flow/bulkrun/run/classification_accuracy_eval_default_20230808_153241_422491/details?wsid=/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourceGroups/promptflow/providers/Microsoft.MachineLearningServices/workspaces/promptflow-eastus&flight=promptfilestorage,PFSourceRun=false",  # noqa: E501
            "data": "azureml://datastores/workspaceblobstore/paths/LocalUpload/312cca2af474e5f895013392b6b38f45/data.jsonl",  # noqa: E501
            "data_portal_url": "https://ml.azure.com/data/datastore/workspaceblobstore/edit?wsid=/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourceGroups/promptflow/providers/Microsoft.MachineLearningServices/workspaces/promptflow-eastus&activeFilePath=LocalUpload/312cca2af474e5f895013392b6b38f45/data.jsonl#browseTab",  # noqa: E501
            "output": "azureml://locations/eastus/workspaces/3e123da1-f9a5-4c91-9234-8d9ffbb39ff5/data/azureml_classification_accuracy_eval_default_20230808_153241_422491_output_data_flow_outputs/versions/1",  # noqa: E501
            "output_portal_url": "https://ml.azure.com/data/azureml_classification_accuracy_eval_default_20230808_153241_422491_output_data_flow_outputs/1/details?wsid=/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourceGroups/promptflow/providers/Microsoft.MachineLearningServices/workspaces/promptflow-eastus",  # noqa: E501
            "run": "web_classification_default_20230804_143634_056856",
            "input_run_portal_url": "https://ml.azure.com/prompts/flow/bulkrun/run/web_classification_default_20230804_143634_056856/details?wsid=/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourceGroups/promptflow/providers/Microsoft.MachineLearningServices/workspaces/promptflow-eastus&flight=promptfilestorage,PFSourceRun=false",  # noqa: E501
        }

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
        assert metrics == {
            "gpt_relevance.variant_1": 1.0,
            "gpt_relevance.variant_0": 1.0,
            "gpt_relevance_pass_rate(%).variant_1": 0.0,
            "gpt_relevance_pass_rate(%).variant_0": 0.0,
        }

    def test_stream_run_logs(self, remote_client, pf):
        run = remote_client.runs.stream(run="4cf2d5e9-c78f-4ab8-a3ee-57675f92fb74")
        assert run.status == "Completed"

    def test_stream_failed_run_logs(self, remote_client, pf, capfd):
        run = remote_client.runs.stream(run="3dfd077a-f071-443e-9c4e-d41531710950")
        out, err = capfd.readouterr()
        print(out)
        assert run.status == "Failed"
        # error info will store in run dict
        assert "error" in run._to_dict()

    def test_visualize(self, remote_client, pf, runtime) -> None:
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run1 = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        remote_client.runs.stream(run=run1.name)
        run2 = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            data=data_path,
            run=run1,
            column_mapping={
                "groundtruth": "${data.answer}",
                "prediction": "${run.outputs.category}",
            },
            runtime=runtime,
        )
        remote_client.runs.stream(run=run2.name)
        remote_client.runs.visualize([run1, run2])

    def test_run_with_additional_includes(self, remote_client, pf, runtime):
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification_with_additional_include",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            inputs_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        run = remote_client.runs.stream(run=run.name)
        assert run.status == "Completed"

        # Test additional includes don't exist
        with pytest.raises(ValueError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification_with_invalid_additional_include",
                data=f"{DATAS_DIR}/webClassification1.jsonl",
                inputs_mapping={"url": "${data.url}"},
                variant="${summarize_text_content.variant_0}",
                runtime=runtime,
            )
        assert "Unable to find additional include ../invalid/file/path" in str(e.value)

    @pytest.mark.skip(reason="Cannot find tools of the flow with symbolic.")
    def test_run_with_symbolic(self, remote_client, pf, runtime, prepare_symbolic_flow):
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification_with_symbolic",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            inputs_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        remote_client.runs.stream(run=run.name)

    def test_run_bulk_without_retry(self, remote_client):
        from azure.core.pipeline.transport._requests_basic import RequestsTransport
        from azure.core.rest._requests_basic import RestRequestsTransportResponse
        from requests import Response

        from promptflow.azure._restclient.flow.models import SubmitBulkRunRequest
        from promptflow.azure._restclient.flow_service_caller import (
            FlowRequestException,
        )

        mock_run = MagicMock()
        mock_run._runtime = "fake_runtime"
        mock_run._to_rest_object.return_value = SubmitBulkRunRequest()
        with patch.object(RunOperations, "_resolve_data_to_asset_id"), patch.object(
            RunOperations, "_resolve_flow"
        ):
            with patch.object(RequestsTransport, "send") as mock_request:
                fake_response = Response()
                # won't retry 500
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

        with patch.object(RunOperations, "_resolve_data_to_asset_id"), patch.object(
            RunOperations, "_resolve_flow"
        ):
            with patch.object(RequestsTransport, "send") as mock_request:
                fake_response = Response()
                # will retry 503
                fake_response.status_code = 503
                fake_response._content = b'{"error": "error"}'
                fake_response._content_consumed = True
                mock_request.return_value = RestRequestsTransportResponse(
                    request=None,
                    internal_response=fake_response,
                )
                with pytest.raises(FlowRequestException):
                    remote_client.runs.create_or_update(run=mock_run)
                assert mock_request.call_count == 4

    def test_pf_run_with_env_var(self, remote_client, pf):
        def create_or_update(run, **kwargs):
            # make run.flow a datastore path uri, so that it can be parsed by AzureMLDatastorePathUri
            run.flow = "azureml://datastores/workspaceblobstore/paths/LocalUpload/not/important/path"
            return run

        with patch.object(RunOperations, "create_or_update") as mock_create_or_update:
            mock_create_or_update.side_effect = create_or_update
            env_var = {"API_BASE": "${azure_open_ai_connection.api_base}"}
            run = pf.run(
                flow=f"{FLOWS_DIR}/print_env_var",
                data=f"{DATAS_DIR}/env_var_names.jsonl",
                environment_variables=env_var,
            )
            assert run._to_rest_object().environment_variables == env_var

    def test_automatic_runtime(self, remote_client, pf):
        from promptflow.azure._restclient.flow_service_caller import FlowServiceCaller

        def submit(*args, **kwargs):
            body = kwargs.get("body", None)
            assert body.runtime_name == "automatic"
            assert body.vm_size is None
            assert body.max_idle_time_seconds is None
            return body

        with patch.object(
            FlowServiceCaller, "submit_bulk_run"
        ) as mock_submit, patch.object(RunOperations, "get"):
            mock_submit.side_effect = submit
            # no runtime provided, will use automatic runtime
            pf.run(
                flow=f"{FLOWS_DIR}/print_env_var",
                data=f"{DATAS_DIR}/env_var_names.jsonl",
            )

    def test_run_data_not_provided(self, pf):
        with pytest.raises(ValueError) as e:
            pf.run(
                flow=f"{FLOWS_DIR}/web_classification",
            )
        assert "at least one of data or run must be provided" in str(e)

    def test_run_without_dump(self, remote_client: PFClient, pf, runtime: str) -> None:
        from promptflow._sdk._orm.run_info import RunInfo
        from promptflow._sdk.exceptions import RunNotFoundError

        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=f"{DATAS_DIR}/webClassification1.jsonl",
            column_mapping={"url": "${data.url}"},
            variant="${summarize_text_content.variant_0}",
            runtime=runtime,
        )
        # cloud run should not dump to database
        with pytest.raises(RunNotFoundError):
            RunInfo.get(run.name)

    def test_input_mapping_with_dict(self, pf, runtime: str):
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"

        pf.run(
            flow=f"{FLOWS_DIR}/flow_with_dict_input",
            data=data_path,
            column_mapping={"key": {"value": "1"}},
            runtime=runtime,
        )

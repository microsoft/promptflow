# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import tempfile
from pathlib import Path
from typing import Callable
from unittest.mock import patch
from datetime import datetime

import pytest
from _constants import PROMPTFLOW_ROOT
from sdk_cli_azure_test.conftest import DATAS_DIR, FLOWS_DIR

from promptflow._constants import TokenKeys
from promptflow._sdk._constants import (
    HOME_PROMPT_FLOW_DIR,
    FlowRunProperties,
    Local2Cloud,
    Local2CloudProperties,
    Local2CloudUserProperties,
    RunStatus,
)
from promptflow._sdk._errors import RunNotFoundError
from promptflow._sdk._pf_client import PFClient as LocalPFClient
from promptflow._sdk.entities import Run
from promptflow._utils.async_utils import async_run_allowing_running_loop
from promptflow.azure import PFClient
from promptflow.azure.operations._async_run_uploader import AsyncRunUploader

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD

EAGER_FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/eager_flows"
RUNS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/runs"
PROMPTY_DIR = PROMPTFLOW_ROOT / "tests/test_configs/prompty"


class Local2CloudTestHelper:
    @staticmethod
    def get_local_pf(run_name: str) -> LocalPFClient:
        """For local to cloud test cases, need a local client."""
        local_pf = LocalPFClient()

        # in replay mode, `randstr` will always return the parameter
        # this will lead to run already exists error for local run
        # so add a try delete to avoid this error
        try:
            local_pf.runs.delete(run_name)
        except RunNotFoundError:
            pass

        return local_pf

    @staticmethod
    def check_local_to_cloud_run(pf: PFClient, run: Run, check_run_details_in_cloud: bool = False) -> Run:
        # check if local run is uploaded
        cloud_run = pf.runs.get(run.name)
        assert cloud_run.display_name == run.display_name
        assert cloud_run.status == run.status
        assert cloud_run._start_time and cloud_run._end_time
        assert datetime.fromisoformat(cloud_run.created_on) == datetime.fromisoformat(run.created_on)
        assert cloud_run.properties["azureml.promptflow.local_to_cloud"] == "true"
        assert cloud_run.properties["azureml.promptflow.snapshot_id"]
        assert cloud_run.properties[Local2CloudProperties.EVAL_ARTIFACTS]
        for token_key in TokenKeys.get_all_values():
            cloud_key = f"{Local2CloudProperties.PREFIX}.{token_key}"
            assert cloud_run.properties[cloud_key] == str(run.properties[FlowRunProperties.SYSTEM_METRICS][token_key])

        # if no description or tags, skip the check, since one could be {} but the other is None
        if run.description:
            assert cloud_run.description == run.description
        if run.tags:
            assert cloud_run.tags == run.tags

        # check run details are actually uploaded to cloud
        if check_run_details_in_cloud:
            run_uploader = AsyncRunUploader._from_run_operations(run_ops=pf.runs)
            run_uploader._set_run(run)
            result_dict = async_run_allowing_running_loop(run_uploader._check_run_details_exist_in_cloud)
            for key, value in result_dict.items():
                assert value, f"Run details {key!r} not found in cloud, run name is {run.name!r}"

        # check run output assets are uploaded to cloud
        original_run_record = pf.runs._get_run_from_run_history(run.name, original_form=True)
        assert original_run_record["runMetadata"]["outputs"][Local2Cloud.ASSET_NAME_DEBUG_INFO]["assetId"]
        assert original_run_record["runMetadata"]["outputs"][Local2Cloud.ASSET_NAME_FLOW_OUTPUTS]["assetId"]

        return cloud_run

    @staticmethod
    def check_run_metrics(pf: PFClient, local_pf: LocalPFClient, run: Run):
        """Check the metrics of the run are uploaded to cloud."""
        local_metrics = local_pf.runs.get_metrics(run.name)
        with patch.object(pf.runs, "_is_system_metric", return_value=False):
            # get the metrics of the run
            cloud_metrics = pf.runs.get_metrics(run.name)

        # check all the user metrics are uploaded to cloud
        for k, v in local_metrics.items():
            assert cloud_metrics.pop(k) == v

        # check all the rest system metrics are uploaded to cloud
        assert cloud_metrics == {
            "__pf__.nodes.grade.completed": 3.0,
            "__pf__.nodes.calculate_accuracy.completed": 1.0,
            "__pf__.nodes.aggregation_assert.completed": 1.0,
            "__pf__.lines.completed": 3.0,
            "__pf__.lines.failed": 0.0,
        }


@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
@pytest.mark.usefixtures(
    "use_secrets_config_file",
    "setup_local_connection",
    "mock_set_headers_with_user_aml_token",
    "single_worker_thread_pool",
    "vcr_recording",
    "mock_isinstance_for_mock_datastore",
    "mock_get_azure_pf_client",
    "mock_trace_destination_to_cloud",
)
class TestFlowRunUpload:
    @pytest.mark.skipif(condition=not pytest.is_live, reason="Bug - 3089145 Replay failed for test 'test_upload_run'")
    def test_upload_run(
        self,
        pf: PFClient,
        randstr: Callable[[str], str],
    ):
        name = randstr("batch_run_name_for_upload")
        local_pf = Local2CloudTestHelper.get_local_pf(name)
        # submit a local batch run.
        run = local_pf.run(
            flow=f"{FLOWS_DIR}/simple_hello_world",
            data=f"{DATAS_DIR}/webClassification3.jsonl",
            name=name,
            column_mapping={"name": "${data.url}"},
            display_name="sdk-cli-test-run-local-to-cloud",
            tags={"sdk-cli-test": "true"},
            description="test sdk local to cloud",
        )
        assert run.status == RunStatus.COMPLETED

        # check the run is uploaded to cloud
        Local2CloudTestHelper.check_local_to_cloud_run(pf, run, check_run_details_in_cloud=True)

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Bug - 3089145 Replay failed for test 'test_upload_run'")
    def test_upload_flex_flow_run_with_yaml(self, pf: PFClient, randstr: Callable[[str], str]):
        name = randstr("flex_run_name_with_yaml_for_upload")
        local_pf = Local2CloudTestHelper.get_local_pf(name)
        # submit a local flex run
        run = local_pf.run(
            flow=Path(f"{EAGER_FLOWS_DIR}/simple_with_yaml"),
            data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
            name=name,
            column_mapping={"input_val": "${data.input_val}"},
            display_name="sdk-cli-test-run-local-to-cloud-flex-with-yaml",
            tags={"sdk-cli-test-flex": "true"},
            description="test sdk local to cloud",
        )
        assert run.status == RunStatus.COMPLETED
        assert "error" not in run._to_dict(), f"Error found: {run._to_dict()['error']}"

        # check the run is uploaded to cloud
        Local2CloudTestHelper.check_local_to_cloud_run(pf, run)

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Bug - 3089145 Replay failed for test 'test_upload_run'")
    def test_upload_flex_flow_run_without_yaml(self, pf: PFClient, randstr: Callable[[str], str]):
        name = randstr("flex_run_name_without_yaml_for_upload")
        local_pf = Local2CloudTestHelper.get_local_pf(name)
        # submit a local flex run
        run = local_pf.run(
            flow="entry:my_flow",
            code=f"{EAGER_FLOWS_DIR}/simple_without_yaml",
            data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
            column_mapping={"input_val": "${data.input_val}"},
            name=name,
            display_name="sdk-cli-test-run-local-to-cloud-flex-without-yaml",
            tags={"sdk-cli-test-flex": "true"},
            description="test sdk local to cloud",
        )
        assert run.status == RunStatus.COMPLETED
        assert "error" not in run._to_dict(), f"Error found: {run._to_dict()['error']}"

        # check the run is uploaded to cloud.
        Local2CloudTestHelper.check_local_to_cloud_run(pf, run)

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Bug - 3089145 Replay failed for test 'test_upload_run'")
    def test_upload_prompty_run(self, pf: PFClient, randstr: Callable[[str], str]):
        # currently prompty run is skipped for upload, this test should be finished without error
        name = randstr("prompty_run_name_for_upload")
        local_pf = Local2CloudTestHelper.get_local_pf(name)
        run = local_pf.run(
            flow=f"{PROMPTY_DIR}/prompty_example.prompty",
            data=f"{DATAS_DIR}/prompty_inputs.jsonl",
            name=name,
        )
        assert run.status == RunStatus.COMPLETED
        assert "error" not in run._to_dict(), f"Error found: {run._to_dict()['error']}"

        # check the run is uploaded to cloud.
        Local2CloudTestHelper.check_local_to_cloud_run(pf, run)

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Bug - 3089145 Replay failed for test 'test_upload_run'")
    def test_upload_run_with_customized_run_properties(self, pf: PFClient, randstr: Callable[[str], str]):
        name = randstr("batch_run_name_for_upload_with_customized_properties")
        local_pf = Local2CloudTestHelper.get_local_pf(name)

        run_type = "test_run_type"

        # submit a local batch run
        run = local_pf._run(
            flow=f"{FLOWS_DIR}/simple_hello_world",
            data=f"{DATAS_DIR}/webClassification3.jsonl",
            name=name,
            column_mapping={"name": "${data.url}"},
            display_name="sdk-cli-test-run-local-to-cloud-with-properties",
            properties={Local2CloudUserProperties.RUN_TYPE: run_type},
        )
        run = local_pf.runs.stream(run.name)
        assert run.status == RunStatus.COMPLETED

        # check the run is uploaded to cloud, and the properties are set correctly
        cloud_run = Local2CloudTestHelper.check_local_to_cloud_run(pf, run)
        assert cloud_run.properties[Local2CloudUserProperties.RUN_TYPE] == run_type

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Bug - 3089145 Replay failed for test 'test_upload_run'")
    def test_upload_eval_run(self, pf: PFClient, randstr: Callable[[str], str]):
        main_run_name = randstr("main_run_name_for_test_upload_eval_run")
        local_pf = Local2CloudTestHelper.get_local_pf(main_run_name)
        main_run = local_pf.run(
            flow=f"{FLOWS_DIR}/simple_hello_world",
            data=f"{DATAS_DIR}/webClassification3.jsonl",
            name=main_run_name,
            column_mapping={"name": "${data.url}"},
        )
        Local2CloudTestHelper.check_local_to_cloud_run(pf, main_run)

        # run an evaluation run
        eval_run_name = randstr("eval_run_name_for_test_upload_eval_run")
        local_pf = Local2CloudTestHelper.get_local_pf(eval_run_name)
        eval_run = local_pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            run=main_run_name,
            name=eval_run_name,
            column_mapping={
                "prediction": "${run.outputs.result}",
                "variant_id": "${run.outputs.result}",
                "groundtruth": "${run.outputs.result}",
            },
        )
        # check the run metrics are uploaded to cloud
        Local2CloudTestHelper.check_run_metrics(pf, local_pf, eval_run)

        # check other run details are uploaded to cloud
        eval_run = Local2CloudTestHelper.check_local_to_cloud_run(pf, eval_run)
        assert eval_run.properties["azureml.promptflow.variant_run_id"] == main_run_name

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Bug - 3089145 Replay failed for test 'test_upload_run'")
    def test_upload_flex_flow_run_with_global_azureml(self, pf: PFClient, randstr: Callable[[str], str]):
        # `get_run_output_path` will internally call `get_config`
        # so also mock that to aovid unexpected side effect
        with patch("promptflow._sdk._configuration.Configuration.get_config", return_value="azureml"), patch(
            "promptflow._sdk._configuration.Configuration.get_run_output_path",
            return_value=HOME_PROMPT_FLOW_DIR.as_posix(),
        ):
            name = randstr("flex_run_name_with_global_azureml_for_upload")
            local_pf = Local2CloudTestHelper.get_local_pf(name)
            # submit a local flex run
            run = local_pf.run(
                flow="entry:my_flow",
                code=f"{EAGER_FLOWS_DIR}/simple_with_config_json",
                data=f"{DATAS_DIR}/simple_eager_flow_data.jsonl",
                column_mapping={"input_val": "${data.input_val}"},
                name=name,
                display_name="sdk-cli-test-run-local-to-cloud-flex-with-global-azureml",
            )
            assert run.status == RunStatus.COMPLETED
            assert "error" not in run._to_dict(), f"Error found: {run._to_dict()['error']}"

            # check the run is uploaded to cloud.
            Local2CloudTestHelper.check_local_to_cloud_run(pf, run)

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Bug - 3089145 Replay failed for test 'test_upload_run'")
    def test_upload_run_pf_eval_dependencies(
        self,
        pf: PFClient,
        randstr: Callable[[str], str],
    ):
        # This test captures promptflow-evals dependencies on private API of promptflow.
        # In case changes are made please reach out to promptflow-evals team to update the dependencies.

        name = randstr("batch_run_name_for_upload")
        local_pf = Local2CloudTestHelper.get_local_pf(name)
        # submit a local batch run.
        run = local_pf.run(
            flow=f"{FLOWS_DIR}/simple_hello_world",
            data=f"{DATAS_DIR}/webClassification3.jsonl",
            name=name,
            column_mapping={"name": "${data.url}"},
            display_name="sdk-cli-test-run-local-to-cloud",
            tags={"sdk-cli-test": "true"},
            description="test sdk local to cloud",
        )
        assert run.status == RunStatus.COMPLETED

        # check the run is uploaded to cloud
        Local2CloudTestHelper.check_local_to_cloud_run(pf, run, check_run_details_in_cloud=True)

        from promptflow._sdk._constants import Local2Cloud
        from promptflow.azure._dependencies._pf_evals import AsyncRunUploader

        async_uploader = AsyncRunUploader._from_run_operations(pf.runs)
        instance_results = local_pf.runs.get_details(run, all_results=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            file_name = Local2Cloud.FLOW_INSTANCE_RESULTS_FILE_NAME
            local_file = Path(temp_dir) / file_name
            instance_results.to_json(local_file, orient="records", lines=True)

            # overriding instance_results.jsonl file
            remote_file = (
                f"{Local2Cloud.BLOB_ROOT_PROMPTFLOW}"
                f"/{Local2Cloud.BLOB_ARTIFACTS}/{run.name}/{Local2Cloud.FLOW_INSTANCE_RESULTS_FILE_NAME}"
            )
            async_run_allowing_running_loop(async_uploader._upload_local_file_to_blob, local_file, remote_file)

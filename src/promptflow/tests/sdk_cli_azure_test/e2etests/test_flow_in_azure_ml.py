import re
from pathlib import Path

import pydash
import pytest
import yaml
from azure.ai.ml import Input, dsl
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import Component, PipelineJob

from promptflow.connections import AzureOpenAIConnection

from .._azure_utils import DEFAULT_TEST_TIMEOUT, PYTEST_TIMEOUT_METHOD

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
MODEL_ROOT = TEST_ROOT / "test_configs/e2e_samples"
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()


def assert_dict_equals_with_skip_fields(item1, item2, skip_fields):
    for fot_key in skip_fields:
        pydash.set_(item1, fot_key, None)
        pydash.set_(item2, fot_key, None)
    assert item1 == item2


def normalize_arm_id(origin_value: str):
    if origin_value:
        m = re.match(
            r"(.*)/subscriptions/[a-z0-9\-]+/resourceGroups/[a-z0-9\-]+/providers/"
            r"Microsoft.MachineLearningServices/workspaces/[a-z0-9\-]+/([a-z]+)/[^/]+/versions/([a-z0-9\-]+)",
            origin_value,
        )
        if m:
            prefix, asset_type, _ = m.groups()
            return (
                f"{prefix}/subscriptions/xxx/resourceGroups/xxx/providers/"
                f"Microsoft.MachineLearningServices/workspaces/xxx/{asset_type}/xxx/versions/xxx"
            )
    return None


def update_saved_spec(component: Component, saved_spec_path: str):
    yaml_text = component._to_yaml()
    saved_spec_path = Path(saved_spec_path)

    yaml_content = yaml.safe_load(yaml_text)
    if yaml_content.get("creation_context"):
        for key in yaml_content.get("creation_context"):
            yaml_content["creation_context"][key] = "xxx"

    for key in ["task.code", "task.environment", "id"]:
        target_value = normalize_arm_id(pydash.get(yaml_content, key))
        if target_value:
            pydash.set_(yaml_content, key, target_value)
    yaml_text = yaml.dump(yaml_content)

    if saved_spec_path.is_file():
        current_spec_text = saved_spec_path.read_text()
        if current_spec_text == yaml_text:
            return
    saved_spec_path.write_text(yaml_text)


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.timeout(timeout=DEFAULT_TEST_TIMEOUT, method=PYTEST_TIMEOUT_METHOD)
@pytest.mark.e2etest
class TestFlowInAzureML:
    @pytest.mark.parametrize(
        "load_params, expected_spec_attrs",
        [
            pytest.param(
                {
                    "component_type": "parallel",
                    "columns_mapping": {
                        "groundtruth": "1",
                        "prediction": "${{batch_run.outputs.category}}",
                    },
                    "environment_variables": {
                        "verbose": "true",
                    },
                },
                {
                    "type": "parallel",
                },
                id="parallel_anonymous",
            ),
            pytest.param(
                {
                    "name": "web_classification_0",
                    "version": "1.0.0",
                    "component_type": "parallel",
                    "description": "Create flows that use large language models to "
                    "classify URLs into multiple categories.",
                    "columns_mapping": {
                        "groundtruth": "1",
                        "prediction": "${{batch_run.outputs.category}}",
                    },
                    "environment_variables": {
                        "verbose": "true",
                    },
                },
                {
                    "name": "web_classification_0",
                    "version": "1.0.0",
                    "description": "Create flows that use large language models to "
                    "classify URLs into multiple categories.",
                    "inputs.groundtruth.default": "1",
                    "inputs.prediction.default": "${{batch_run.outputs.category}}",
                    "type": "parallel",
                },
                id="parallel",
            ),
        ],
    )
    def test_flow_as_component(
        self,
        azure_open_ai_connection: AzureOpenAIConnection,
        temp_output_dir,
        pf,
        load_params: dict,
        expected_spec_attrs: dict,
        request,
    ) -> None:

        flows_dir = "./tests/test_configs/flows"

        flow_func: Component = pf.load_as_component(
            f"{flows_dir}/web_classification",
            **load_params,
        )

        update_saved_spec(flow_func, f"./tests/test_configs/flows/saved_component_spec/{request.node.callspec.id}.yaml")

        component_dict = flow_func._to_dict()
        slimmed_created_component_attrs = {key: pydash.get(component_dict, key) for key in expected_spec_attrs.keys()}
        assert slimmed_created_component_attrs == expected_spec_attrs

    def test_flow_as_component_in_dsl_pipeline(
        self, azure_open_ai_connection: AzureOpenAIConnection, temp_output_dir, pf
    ) -> None:

        flows_dir = "./tests/test_configs/flows"

        flow_func: Component = pf.load_as_component(
            f"{flows_dir}/web_classification",
            component_type="parallel",
            columns_mapping={
                "groundtruth": "${data.answer}",
                "url": "${data.url}",
            },
            environment_variables={
                "verbose": "true",
            },
        )

        @dsl.pipeline
        def pipeline_with_flow(input_data):
            flow_node = flow_func(
                data=input_data,
                connections={
                    "summarize_text_content": {
                        "deployment_name": "test_deployment_name",
                    }
                },
            )
            flow_node.logging_level = "DEBUG"
            return flow_node.outputs

        pipeline: PipelineJob = pipeline_with_flow(
            input_data=Input(path=f"{flows_dir}/web_classification_input_dir", type=AssetTypes.URI_FOLDER),
        )
        # compute cluster doesn't have access to azurecr for now, so the submitted job will fail in building image stage
        pipeline.settings.default_compute = "cpu-cluster"

        created_job: PipelineJob = pf.ml_client.jobs.create_or_update(pipeline)
        assert created_job.id
        assert created_job.jobs["flow_node"].logging_level == "DEBUG"

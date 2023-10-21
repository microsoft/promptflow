import re
from pathlib import Path

import pydash
import pytest
import yaml
from azure.ai.ml import load_component
from azure.ai.ml.entities import Component

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
    saved_spec_path.parent.mkdir(parents=True, exist_ok=True)
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
                    "name": "web_classification_4",
                    "version": "1.0.0",
                    "description": "Create flows that use large language models to "
                    "classify URLs into multiple categories.",
                    "environment_variables": {
                        "verbose": "true",
                    },
                },
                {
                    "name": "web_classification_4",
                    "version": "1.0.0",
                    "description": "Create flows that use large language models to "
                    "classify URLs into multiple categories.",
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
        ml_client,
        load_params: dict,
        expected_spec_attrs: dict,
        request,
    ) -> None:
        # keep the simplest test here, more tests are in azure-ai-ml

        flows_dir = "./tests/test_configs/flows"

        flow_func: Component = load_component(
            f"{flows_dir}/web_classification/flow.dag.yaml", params_override=[load_params]
        )

        # TODO: snapshot of flow component changed every time?
        created_component = ml_client.components.create_or_update(flow_func, is_anonymous=True)

        update_saved_spec(
            created_component, f"./tests/test_configs/flows/saved_component_spec/{request.node.callspec.id}.yaml"
        )

        component_dict = created_component._to_dict()
        slimmed_created_component_attrs = {key: pydash.get(component_dict, key) for key in expected_spec_attrs.keys()}
        assert slimmed_created_component_attrs == expected_spec_attrs

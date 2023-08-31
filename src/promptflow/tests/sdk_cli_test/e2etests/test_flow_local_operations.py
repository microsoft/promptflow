import os.path
import shutil
import sys
import tempfile
from pathlib import Path

import mock
import pytest
import yaml

from promptflow.connections import AzureOpenAIConnection

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."

TEST_ROOT = Path(__file__).parent.parent.parent
MODEL_ROOT = TEST_ROOT / "test_configs/e2e_samples"
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
FLOWS_DIR = "./tests/test_configs/flows"
DATAS_DIR = "./tests/test_configs/datas"


def e2e_test_docker_build_and_run(output_path):
    """Build and run the docker image locally.
    This function is for adhoc local test and need to run on a dev machine with docker installed.
    """
    import subprocess

    subprocess.check_output(["docker", "build", ".", "-t", "test"], cwd=output_path)
    subprocess.check_output(["docker", "tag", "test", "elliotz/promptflow-export-result:latest"], cwd=output_path)

    subprocess.check_output(
        [
            "docker",
            "run",
            "-e",
            "CUSTOM_CONNECTION_AZURE_OPENAI_API_KEY='xxx'" "elliotz/promptflow-export-result:latest",
        ],
        cwd=output_path,
    )


@pytest.fixture
def setup_connections(azure_open_ai_connection: AzureOpenAIConnection):
    _ = {
        "azure_open_ai_connection": azure_open_ai_connection,
    }
    from promptflow._sdk._pf_client import PFClient
    from promptflow._sdk.entities._connection import _Connection

    _client = PFClient()
    _client.connections.create_or_update(
        _Connection._load(
            data={
                "name": "custom_connection",
                "type": "custom",
                "configs": {
                    "CHAT_DEPLOYMENT_NAME": "gpt-35-turbo",
                    "AZURE_OPENAI_API_BASE": azure_open_ai_connection.api_base,
                },
                "secrets": {
                    "AZURE_OPENAI_API_KEY": azure_open_ai_connection.api_key,
                },
            }
        )
    )
    _client.connections.create_or_update(
        _Connection._load(
            data={
                "name": "azure_open_ai_connection",
                "type": "azure_open_ai",
                "api_type": azure_open_ai_connection.api_type,
                "api_base": azure_open_ai_connection.api_base,
                "api_version": azure_open_ai_connection.api_version,
                "api_key": azure_open_ai_connection.api_key,
            }
        )
    )


@pytest.mark.usefixtures("use_secrets_config_file", "setup_connections")
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestFlowLocalOperations:
    def test_flow_build_as_docker(self, pf) -> None:
        source = f"{FLOWS_DIR}/intent-copilot"

        output_path = f"{FLOWS_DIR}/export/linux"
        shutil.rmtree(output_path, ignore_errors=True)

        (Path(source) / ".runs").mkdir(exist_ok=True)
        (Path(source) / ".runs" / "dummy_run_file").touch()

        with mock.patch("promptflow._sdk.operations._flow_operations.generate_random_string") as mock_random_string:
            mock_random_string.return_value = "dummy1"
            pf.flows.build(
                flow=source,
                output=output_path,
                format="docker",
            )
            assert mock_random_string.call_count == 1

        # check if .amlignore works
        assert os.path.isfile(f"{source}/.promptflow/flow.tools.json")
        assert not (Path(output_path) / "flow" / ".promptflow" / "flow.tools.json").exists()
        assert os.path.isdir(f"{source}/data")
        assert not (Path(output_path) / "flow" / "data").exists()

        # check if .runs is ignored by default
        assert os.path.isfile(f"{source}/.runs/dummy_run_file")
        assert not (Path(output_path) / "flow" / ".runs" / "dummy_run_file").exists()

        # e2e_test_docker_build_and_run(output_path)

    @pytest.mark.skipif(sys.platform == "darwin", reason="Skip on Mac")
    def test_flow_build_as_docker_with_additional_includes(self, pf) -> None:
        source = f"{FLOWS_DIR}/web_classification_with_additional_include"
        with tempfile.TemporaryDirectory() as temp_dir:
            pf.flows.build(
                flow=source,
                output=temp_dir,
                format="docker",
            )

            for additional_include in [
                "../external_files/convert_to_dict.py",
                "../external_files/fetch_text_content_from_url.py",
                "../external_files/summarize_text_content.jinja2",
            ]:
                additional_include_path = Path(source, additional_include)
                target_path = Path(temp_dir, "flow", additional_include_path.name)

                assert target_path.is_file()
                assert target_path.read_text() == additional_include_path.read_text()

    @pytest.mark.skipif(sys.platform == "darwin", reason="Skip on Mac")
    def test_flow_build_as_docker_with_variant(self, pf) -> None:
        source = f"{FLOWS_DIR}/web_classification_with_additional_include"

        with tempfile.TemporaryDirectory() as temp_dir:
            pf.flows.build(
                flow=source,
                output=temp_dir,
                format="docker",
                variant="${summarize_text_content.variant_0}",
            )

            new_flow_dag_path = Path(temp_dir, "flow", "flow.dag.yaml")
            flow_dag = yaml.safe_load(new_flow_dag_path.read_text())
            target_node = next(filter(lambda x: x["name"] == "summarize_text_content", flow_dag["nodes"]))
            target_node.pop("name")
            assert target_node == flow_dag["node_variants"]["summarize_text_content"]["variants"]["variant_0"]["node"]

import os.path
import shutil
from pathlib import Path

import pytest

from promptflow._sdk.entities._flow import Flow
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


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestFlowLocalOperations:
    def test_flow_export_as_docker(self, azure_open_ai_connection: AzureOpenAIConnection) -> None:
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

        source = f"{FLOWS_DIR}/intent-copilot"
        flow = Flow.load(source)

        output_path = f"{FLOWS_DIR}/export/linux"
        shutil.rmtree(output_path, ignore_errors=True)

        from promptflow._sdk.entities._flow import FlowProtected

        flow.__class__ = FlowProtected

        (Path(source) / ".runs").mkdir(exist_ok=True)
        (Path(source) / ".runs" / "dummy_run_file").touch()

        flow.export(
            output=output_path,
            format="docker",
        )

        # check if .amlignore works
        assert os.path.isfile(f"{source}/.promptflow/flow.tools.json")
        assert not (Path(output_path) / "flow" / ".promptflow" / "flow.tools.json").exists()
        assert os.path.isdir(f"{source}/data")
        assert not (Path(output_path) / "flow" / "data").exists()

        # check if .runs is ignored by default
        assert os.path.isfile(f"{source}/.runs/dummy_run_file")
        assert not (Path(output_path) / "flow" / ".runs" / "dummy_run_file").exists()

        # e2e_test_docker_build_and_run(output_path)

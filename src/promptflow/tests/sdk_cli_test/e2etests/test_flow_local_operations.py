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
    import tempfile

    subprocess.check_output(["docker", "build", ".", "-t", "test"], cwd=output_path)
    subprocess.check_output(
        ["docker", "tag", "test", "elliotz/promptflow-export-result:latest"],
        cwd=output_path,
    )

    migration_secret_name = "MIGRATION_SECRET"
    subprocess.call(["docker", "swarm", "init"], cwd=output_path)

    service_name = "test_service"
    subprocess.call(["docker", "service", "rm", service_name], cwd=output_path)
    with tempfile.TemporaryDirectory() as temp_dir:
        secret_file = Path(temp_dir) / "secret.txt"
        secret_file.write_text("123")
        subprocess.call(
            [
                "docker",
                "secret",
                "create",
                migration_secret_name,
                secret_file.as_posix(),
            ],
            cwd=output_path,
        )
    subprocess.call(
        [
            "docker",
            "secret",
            "create",
            migration_secret_name,
            os.path.join(output_path, migration_secret_name),
        ],
        cwd=output_path,
    )
    subprocess.check_output(
        [
            "docker",
            "service",
            "create",
            "--secret",
            migration_secret_name,
            "--name",
            service_name,
            "--publish",
            "8080:8080",
            "elliotz/promptflow-export-result:latest",
        ],
        cwd=output_path,
    )


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestFlowLocalOperations:
    def test_flow_export_as_docker(
        self, azure_open_ai_connection: AzureOpenAIConnection
    ) -> None:
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
        dummy_migration_secret = "123"

        (Path(source) / ".runs").mkdir(exist_ok=True)
        (Path(source) / ".runs" / "dummy_run_file").touch()

        flow.export(
            output=output_path,
            format="docker",
            migration_secret=dummy_migration_secret,
        )

        # check if .amlignore works
        assert os.path.isfile(f"{source}/.promptflow/flow.tools.json")
        assert not (
            Path(output_path) / "flow" / ".promptflow" / "flow.tools.json"
        ).exists()
        assert os.path.isdir(f"{source}/data")
        assert not (Path(output_path) / "flow" / "data").exists()

        # check if .runs is ignored by default
        assert os.path.isfile(f"{source}/.runs/dummy_run_file")
        assert not (Path(output_path) / "flow" / ".runs" / "dummy_run_file").exists()

        # e2e_test_docker_build_and_run(output_path)

    def test_get_metrics_format(self, local_client, pf) -> None:
        # create run with metrics
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run1 = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"url": "${data.url}"},
        )
        run2 = pf.run(
            flow=f"{FLOWS_DIR}/classification_accuracy_evaluation",
            data=data_path,
            run=run1.name,
            column_mapping={
                "groundtruth": "${data.answer}",
                "prediction": "${run.outputs.category}",
                "variant_id": "${data.variant_id}",
            },
        )
        # ensure the result is a flatten dict
        assert local_client.runs.get_metrics(run2.name).keys() == {"accuracy"}

    def test_get_detail_format(self, local_client, pf) -> None:
        data_path = f"{DATAS_DIR}/webClassification3.jsonl"
        run = pf.run(
            flow=f"{FLOWS_DIR}/web_classification",
            data=data_path,
            column_mapping={"url": "${data.url}"},
        )
        # data is a jsonl file, so we can know the number of line runs
        with open(data_path, "r") as f:
            data = f.readlines()
        number_of_lines = len(data)

        from promptflow._sdk.operations._local_storage_operations import (
            LocalStorageOperations,
        )

        local_storage = LocalStorageOperations(local_client.runs.get(run.name))
        detail = local_storage.load_detail()

        assert isinstance(detail, dict)
        # flow runs
        assert "flow_runs" in detail
        assert isinstance(detail["flow_runs"], list)
        assert len(detail["flow_runs"]) == number_of_lines
        # node runs
        assert "node_runs" in detail
        assert isinstance(detail["node_runs"], list)

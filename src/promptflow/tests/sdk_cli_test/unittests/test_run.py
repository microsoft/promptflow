# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from marshmallow import ValidationError

from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY, NODES
from promptflow._sdk._errors import InvalidFlowError
from promptflow._sdk._load_functions import load_run
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk._run_functions import create_yaml_run
from promptflow._sdk.entities import Run
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._sdk.operations._run_submitter import RunSubmitter, overwrite_variant, variant_overwrite_context

PROMOTFLOW_ROOT = Path(__file__) / "../../../.."
FLOWS_DIR = Path("./tests/test_configs/flows")
RUNS_DIR = Path("./tests/test_configs/runs")
DATAS_DIR = Path("./tests/test_configs/datas")


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestRun:
    def test_overwrite_variant_context(self):
        with variant_overwrite_context(
            flow_path=FLOWS_DIR / "web_classification", tuning_node="summarize_text_content", variant="variant_0"
        ) as flow:
            with open(flow.path) as f:
                flow_dag = yaml.safe_load(f)
            node_name_2_node = {node["name"]: node for node in flow_dag[NODES]}
            node = node_name_2_node["summarize_text_content"]
            assert node["inputs"]["temperature"] == "0.2"

    def test_overwrite_connections(self):
        with variant_overwrite_context(
            flow_path=FLOWS_DIR / "web_classification",
            connections={"classify_with_llm": {"connection": "azure_open_ai", "deployment_name": "gpt-35-turbo"}},
        ) as flow:
            with open(flow.path) as f:
                flow_dag = yaml.safe_load(f)
            node_name_2_node = {node["name"]: node for node in flow_dag[NODES]}
            node = node_name_2_node["classify_with_llm"]
            assert node["connection"] == "azure_open_ai"
            assert node["inputs"]["deployment_name"] == "gpt-35-turbo"

    @pytest.mark.parametrize(
        "connections, error_message",
        [
            (
                {
                    "classify_with_llm": {
                        "connection": "azure_open_ai",
                        "deployment_name": "gpt-35-turbo",
                        "unsupported": 1,
                    }
                },
                "Unsupported llm connection overwrite keys",
            ),
            ("str", "Invalid connections overwrite format: str"),
            ({"not_exist": 1}, "Node not_exist not found in flow"),
            ({"classify_with_llm": 1}, "Invalid connection overwrite format: 1, only dict is supported."),
        ],
    )
    def test_overwrite_connections_invalid(self, connections, error_message):
        with pytest.raises(InvalidFlowError) as e:
            with variant_overwrite_context(
                flow_path=FLOWS_DIR / "web_classification",
                connections=connections,
            ):
                pass
        assert error_message in str(e.value)

    def test_load_run(self):
        input_dict = {
            "data": (DATAS_DIR / "webClassification1.jsonl").resolve().as_posix(),
            "column_mapping": {"context": "${data.context}"},
            "flow": (FLOWS_DIR / "web_classification").resolve().as_posix(),
        }
        bulk_run = Run._load_from_dict(
            data=input_dict, context={BASE_PATH_CONTEXT_KEY: FLOWS_DIR}, additional_message=""
        )
        assert isinstance(bulk_run, Run)

    def test_dot_env_resolve(self):
        run_id = str(uuid.uuid4())
        source = f"{RUNS_DIR}/sample_bulk_run.yaml"
        run = load_run(source=source, params_override=[{"name": run_id}])
        assert run.environment_variables == {"FOO": "BAR"}

    def test_data_not_exist_validation_error(self):
        source = f"{RUNS_DIR}/sample_bulk_run.yaml"
        with pytest.raises(ValidationError) as e:
            load_run(source=source, params_override=[{"data": "not_exist"}])

        assert "Can't find directory or file" in str(e.value)
        assert "Invalid remote path." in str(e.value)

    @pytest.mark.parametrize(
        "source, error_msg",
        [
            (f"{RUNS_DIR}/illegal/extra_field.yaml", "Unknown field"),
            (f"{RUNS_DIR}/illegal/non_exist_data.yaml", "Can't find directory or file"),
        ],
    )
    def test_invalid_yaml(self, source, error_msg):
        with pytest.raises(ValidationError) as e:
            create_yaml_run(source=source)
        assert error_msg in str(e.value)

    def test_run_bulk_invalid_params(self, pf):
        # Test if function raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            pf.run(flow="invalid_path", data="fake_data")

        with pytest.raises(FileNotFoundError):
            pf.run(flow="invalid_path", data="fake_data", batch_run="fake_run")

    def test_overwrite_variant(self, temp_output_dir):
        # Create a temporary flow file
        tmp_path = Path(temp_output_dir)
        flow_file = tmp_path / "flow.yaml"
        flow_file.write_text(
            """
nodes:
  - name: node1
    use_variants: true
    variant_id: default
    inputs:
      param1: value1
      param2: value2
node_variants:
  node1:
    variants:
      variant1:
        node:
          inputs:
            param1: value1_variant1
            param2: value2_variant1
        """
        )

        # Test if function raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            overwrite_variant(tmp_path / "invalid_path", "node1", "variant1")

        # Test if function raises InvalidFlowError
        with pytest.raises(InvalidFlowError):
            overwrite_variant(flow_file, "node3", "variant1")
        with pytest.raises(InvalidFlowError):
            overwrite_variant(flow_file, "node1", "variant3")

        # Test if function overwrites variant correctly
        overwrite_variant(flow_file, "node1", "variant1")
        with open(flow_file, "r") as f:
            flow_dag = yaml.safe_load(f)
        assert flow_dag["nodes"][0]["inputs"]["param1"] == "value1_variant1"
        assert flow_dag["nodes"][0]["inputs"]["param2"] == "value2_variant1"

    @patch("promptflow._sdk.operations._run_operations.RunOperations.update")
    def test_submit(self, mock_update):
        # Define input parameters
        flow_path = f"{FLOWS_DIR}/web_classification"
        client = PFClient()
        run_submitter = RunSubmitter(client.runs)
        run = Run(
            name=str(uuid.uuid4()),
            flow=Path(flow_path),
            data=f"{DATAS_DIR}/webClassification3.jsonl",
        )
        # Submit run
        run_submitter.submit(run)

        # Check if Run.update method was called
        mock_update.assert_called_once()

    def test_flow_run_with_non_english_inputs(self, pf):
        flow_path = f"{FLOWS_DIR}/flow_with_non_english_input"
        data = f"{FLOWS_DIR}/flow_with_non_english_input/data.jsonl"
        run = pf.run(flow=flow_path, data=data, column_mapping={"text": "${data.text}"})
        local_storage = LocalStorageOperations(run=run)
        outputs = local_storage.load_outputs()
        assert outputs == {"output": ["Hello 123 日本語", "World 123 日本語"]}

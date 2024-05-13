# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import copy
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from promptflow._sdk._constants import BASE_PATH_CONTEXT_KEY, NODES
from promptflow._sdk._errors import InvalidFlowError
from promptflow._sdk._load_functions import load_flow, load_run
from promptflow._sdk._orchestrator import RunSubmitter, flow_overwrite_context, overwrite_variant
from promptflow._sdk._pf_client import PFClient
from promptflow._sdk._run_functions import create_yaml_run
from promptflow._sdk._utilities.general_utils import callable_to_entry_string
from promptflow._sdk.entities import Run
from promptflow._sdk.entities._flows import Flow
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._utils.context_utils import inject_sys_path
from promptflow._utils.yaml_utils import load_yaml
from promptflow.connections import AzureOpenAIConnection
from promptflow.exceptions import UserErrorException, ValidationException

FLOWS_DIR = Path("./tests/test_configs/flows")
EAGER_FLOWS_DIR = Path("./tests/test_configs/eager_flows")
RUNS_DIR = Path("./tests/test_configs/runs")
DATAS_DIR = Path("./tests/test_configs/datas")


@pytest.fixture
def test_flow() -> Flow:
    flow_path = f"{FLOWS_DIR}/web_classification"
    return load_flow(flow_path)


async def my_async_func():
    pass


@pytest.mark.sdk_test
@pytest.mark.unittest
class TestRun:
    def test_overwrite_variant_context(self, test_flow: Flow):
        with flow_overwrite_context(flow=test_flow, tuning_node="summarize_text_content", variant="variant_0") as flow:
            with open(flow.path) as f:
                flow_dag = load_yaml(f)
            node_name_2_node = {node["name"]: node for node in flow_dag[NODES]}
            node = node_name_2_node["summarize_text_content"]
            assert node["inputs"]["temperature"] == "0.2"

    def test_overwrite_connections(self, test_flow: Flow):
        with flow_overwrite_context(
            flow=test_flow,
            connections={"classify_with_llm": {"connection": "azure_open_ai", "deployment_name": "gpt-35-turbo"}},
        ) as flow:
            with open(flow.path) as f:
                flow_dag = load_yaml(f)
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
    def test_overwrite_connections_invalid(self, connections, error_message, test_flow: Flow):
        with pytest.raises(InvalidFlowError) as e:
            with flow_overwrite_context(
                flow=test_flow,
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

    def test_run_invalid_flow_path(self):
        run_id = str(uuid.uuid4())
        source = f"{RUNS_DIR}/bulk_run_invalid_flow_path.yaml"
        with pytest.raises(ValidationException) as e:
            load_run(source=source, params_override=[{"name": run_id}])
        assert "Can't find directory or file in resolved absolute path:" in str(e.value)

    def test_run_invalid_remote_flow(self):
        run_id = str(uuid.uuid4())
        source = f"{RUNS_DIR}/bulk_run_invalid_remote_flow_str.yaml"
        with pytest.raises(ValidationException) as e:
            load_run(source=source, params_override=[{"name": run_id}])
        assert "Invalid remote flow path. Currently only azureml:<flow-name> is supported" in str(e.value)

    def test_data_not_exist_validation_error(self):
        source = f"{RUNS_DIR}/sample_bulk_run.yaml"
        with pytest.raises(ValidationException) as e:
            load_run(source=source, params_override=[{"data": "not_exist"}])

        assert "Can't find directory or file" in str(e.value)
        assert "Invalid remote path." in str(e.value)

    @pytest.mark.parametrize(
        "source, error_msg",
        [
            (f"{RUNS_DIR}/illegal/non_exist_data.yaml", "Can't find directory or file"),
        ],
    )
    def test_invalid_yaml(self, source, error_msg):
        with pytest.raises(ValidationException) as e:
            create_yaml_run(source=source)
        assert error_msg in str(e.value)

    def test_run_bulk_invalid_params(self, pf):
        # Test if function raises FileNotFoundError
        with pytest.raises(UserErrorException):
            pf.run(flow="invalid_path", data="fake_data")

        with pytest.raises(UserErrorException):
            pf.run(flow="invalid_path", data="fake_data", batch_run="fake_run")

    def test_overwrite_variant(self):
        flow_dag = {
            "nodes": [
                {
                    "name": "node1",
                    "use_variants": True,
                    "variant_id": "default",
                    "inputs": {
                        "param1": "value1",
                        "param2": "value2",
                    },
                },
            ],
            "node_variants": {
                "node1": {
                    "default_variant_id": "variant1",
                    "variants": {
                        "variant1": {
                            "node": {
                                "inputs": {
                                    "param1": "value1_variant1",
                                    "param2": "value2_variant1",
                                },
                            },
                        },
                    },
                },
            },
        }

        # Test if function raises InvalidFlowError
        with pytest.raises(InvalidFlowError):
            overwrite_variant(flow_dag, "node3", "variant1")
        with pytest.raises(InvalidFlowError):
            overwrite_variant(flow_dag, "node1", "variant3")

        # Test if function overwrites variant correctly
        dag = copy.deepcopy(flow_dag)
        overwrite_variant(dag, "node1", "variant1")
        assert dag["nodes"][0]["inputs"]["param1"] == "value1_variant1"
        assert dag["nodes"][0]["inputs"]["param2"] == "value2_variant1"

        # test overwrite default variant
        dag = copy.deepcopy(flow_dag)
        overwrite_variant(dag)
        assert dag["nodes"][0]["inputs"]["param1"] == "value1_variant1"
        assert dag["nodes"][0]["inputs"]["param2"] == "value2_variant1"

    @patch("promptflow._sdk.operations._run_operations.RunOperations.update")
    def test_submit(self, mock_update):
        # Define input parameters
        flow_path = f"{FLOWS_DIR}/web_classification"
        client = PFClient()
        run_submitter = RunSubmitter(client)
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
        # assert non english in output.jsonl
        output_jsonl_path = local_storage._outputs_path
        with open(output_jsonl_path, "r", encoding="utf-8") as f:
            outputs_text = f.readlines()
            assert outputs_text == [
                '{"line_number": 0, "output": "Hello 123 日本語"}\n',
                '{"line_number": 1, "output": "World 123 日本語"}\n',
            ]
        # assert non english in memory
        outputs = local_storage.load_outputs()
        assert outputs == {"output": ["Hello 123 日本語", "World 123 日本語"]}

    @pytest.mark.usefixtures("enable_logger_propagate")
    def test_flow_run_with_unknown_field(self, caplog):
        run_yaml = Path(RUNS_DIR) / "sample_bulk_run.yaml"
        load_run(source=run_yaml, params_override=[{"unknown_field": "unknown_value"}])
        assert "Unknown fields found" in caplog.text

    def test_callable_to_entry_string(self):

        assert callable_to_entry_string(test_flow) == "sdk_cli_test.unittests.test_run:test_flow"

        assert callable_to_entry_string(my_async_func) == "sdk_cli_test.unittests.test_run:my_async_func"

        with inject_sys_path(f"{EAGER_FLOWS_DIR}/multiple_entries"):
            from entry2 import my_flow2

            assert callable_to_entry_string(my_flow2) == "entry2:my_flow2"

    def test_callable_to_entry_string_not_supported(self):
        non_callable = "not a callable"

        def function():
            pass

        class MyClass:
            def method(self):
                pass

            @classmethod
            def class_method(cls):
                pass

            @staticmethod
            def static_method():
                pass

        obj = MyClass()

        for entry in [non_callable, function, obj.method, obj.class_method, obj.static_method, MyClass.class_method]:
            with pytest.raises(UserErrorException):
                callable_to_entry_string(entry)

    @pytest.mark.parametrize(
        "init_val, expected_error_msg",
        [
            ("val", "Invalid init kwargs: val"),
            (
                {"obj_input": AzureOpenAIConnection(api_base="fake_api_base")},
                "Expecting a json serializable dictionary.",
            ),
        ],
    )
    def test_invalid_init_kwargs(self, pf, init_val, expected_error_msg):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/basic_callable_class")
        with pytest.raises(UserErrorException) as e:
            pf.run(flow=flow_path, data=f"{EAGER_FLOWS_DIR}/basic_callable_class/inputs.jsonl", init=init_val)
        assert expected_error_msg in str(e.value)

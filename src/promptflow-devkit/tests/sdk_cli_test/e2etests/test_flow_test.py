import logging
import sys
import tempfile
from dataclasses import is_dataclass
from pathlib import Path

import papermill
import pydash
import pytest
from _constants import PROMPTFLOW_ROOT
from marshmallow import ValidationError

from promptflow._sdk._constants import LOGGER_NAME
from promptflow._sdk._pf_client import PFClient
from promptflow._utils.context_utils import _change_working_dir
from promptflow.core import AzureOpenAIModelConfiguration, OpenAIModelConfiguration
from promptflow.core._utils import init_executable
from promptflow.exceptions import UserErrorException
from promptflow.executor._errors import FlowEntryInitializationError, InputNotFound

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
CONNECTION_FILE = (PROMPTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
FLOWS_DIR = (TEST_ROOT / "test_configs/flows").resolve().absolute().as_posix()
EAGER_FLOWS_DIR = (TEST_ROOT / "test_configs/eager_flows").resolve().absolute().as_posix()
FLOW_RESULT_KEYS = ["category", "evidence"]
DATA_ROOT = TEST_ROOT / "test_configs/datas"

_client = PFClient()


def clear_module_cache(module_name):
    try:
        del sys.modules[module_name]
    except Exception:
        pass


@pytest.mark.usefixtures(
    "use_secrets_config_file", "recording_injection", "setup_local_connection", "install_custom_tool_pkg"
)
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestFlowTest:
    def test_pf_test_flow(self):
        inputs = {"url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g", "answer": "Channel", "evidence": "Url"}
        flow_path = Path(f"{FLOWS_DIR}/web_classification").absolute()

        result = _client.test(flow=flow_path, inputs=inputs)
        assert all([key in FLOW_RESULT_KEYS for key in result])

        result = _client.test(flow=f"{FLOWS_DIR}/web_classification")
        assert all([key in FLOW_RESULT_KEYS for key in result])

        # Test flow test with sample input file
        result = _client.test(flow=flow_path, inputs=DATA_ROOT / "webClassification1.jsonl")
        assert all([key in FLOW_RESULT_KEYS for key in result])

        # Test flow test with invalid input file
        with pytest.raises(UserErrorException) as ex:
            _client.test(flow=flow_path, inputs=DATA_ROOT / "invalid_path.json")
        assert "Cannot find inputs file" in ex.value.message

        # Test flow test with invalid file extension
        with pytest.raises(UserErrorException) as ex:
            _client.test(flow=flow_path, inputs=DATA_ROOT / "logo.jpg")
        assert "Only support jsonl or json file as input" in ex.value.message

    def test_pf_test_flow_with_package_tool_with_custom_strong_type_connection(self, install_custom_tool_pkg):
        inputs = {"text": "Hello World!"}
        flow_path = Path(f"{FLOWS_DIR}/flow_with_package_tool_with_custom_strong_type_connection").absolute()

        # Test that connection would be custom strong type in flow
        result = _client.test(flow=flow_path, inputs=inputs)
        assert result == {"out": "connection_value is MyFirstConnection: True"}

        # Test node run
        result = _client.test(flow=flow_path, inputs={"input_text": "Hello World!"}, node="My_Second_Tool_usi3")
        assert result == "Hello World!This is my first custom connection."

    def test_pf_test_flow_with_package_tool_with_custom_connection_as_input_value(self, install_custom_tool_pkg):
        # Prepare custom connection
        from promptflow.connections import CustomConnection

        conn = CustomConnection(name="custom_connection_3", secrets={"api_key": "test"}, configs={"api_base": "test"})
        _client.connections.create_or_update(conn)

        inputs = {"text": "Hello World!"}
        flow_path = Path(f"{FLOWS_DIR}/flow_with_package_tool_with_custom_connection").absolute()

        # Test that connection would be custom strong type in flow
        result = _client.test(flow=flow_path, inputs=inputs)
        assert result == {"out": "connection_value is MyFirstConnection: True"}

    def test_pf_test_flow_with_script_tool_with_custom_strong_type_connection(self):
        # Prepare custom connection
        from promptflow.connections import CustomConnection

        conn = CustomConnection(name="custom_connection_2", secrets={"api_key": "test"}, configs={"api_url": "test"})
        _client.connections.create_or_update(conn)

        inputs = {"text": "Hello World!"}
        flow_path = Path(f"{FLOWS_DIR}/flow_with_script_tool_with_custom_strong_type_connection").absolute()

        # Test that connection would be custom strong type in flow
        result = _client.test(flow=flow_path, inputs=inputs)
        assert result == {"out": "connection_value is MyCustomConnection: True"}

        # Test node run
        result = _client.test(flow=flow_path, inputs={"input_param": "Hello World!"}, node="my_script_tool")
        assert result == "connection_value is MyCustomConnection: True"

    def test_pf_test_with_streaming_output(self):
        flow_path = Path(f"{FLOWS_DIR}/chat_flow_with_stream_output")
        result = _client.test(flow=flow_path)
        chat_output = result["answer"]
        # assert isinstance(chat_output, GeneratorType)
        assert "".join(chat_output)

        flow_path = Path(f"{FLOWS_DIR}/basic_with_builtin_llm_node")
        result = _client.test(flow=flow_path)
        chat_output = result["output"]
        assert isinstance(chat_output, str)

    def test_pf_test_node(self):
        inputs = {"classify_with_llm.output": '{"category": "App", "evidence": "URL"}'}
        flow_path = Path(f"{FLOWS_DIR}/web_classification").absolute()

        result = _client.test(flow=flow_path, inputs=inputs, node="convert_to_dict")
        assert all([key in FLOW_RESULT_KEYS for key in result])

    def test_pf_test_flow_with_variant(self):
        inputs = {"url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g", "answer": "Channel", "evidence": "Url"}

        result = _client.test(
            flow=f"{FLOWS_DIR}/web_classification", inputs=inputs, variant="${summarize_text_content.variant_1}"
        )
        assert all([key in FLOW_RESULT_KEYS for key in result])

    @pytest.mark.skip("TODO this test case failed in windows and Mac")
    def test_pf_test_with_additional_includes(self, caplog):
        from promptflow._sdk._version import VERSION

        print(VERSION)
        with caplog.at_level(level=logging.WARNING, logger=LOGGER_NAME):
            inputs = {"url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g", "answer": "Channel", "evidence": "Url"}
            result = _client.test(flow=f"{FLOWS_DIR}/web_classification_with_additional_include", inputs=inputs)
        duplicate_file_content = "Found duplicate file in additional includes"
        assert any([duplicate_file_content in record.message for record in caplog.records])
        assert all([key in FLOW_RESULT_KEYS for key in result])

        inputs = {"classify_with_llm.output": '{"category": "App", "evidence": "URL"}'}
        result = _client.test(flow=f"{FLOWS_DIR}/web_classification", inputs=inputs, node="convert_to_dict")
        assert all([key in FLOW_RESULT_KEYS for key in result])

        # Test additional includes don't exist
        with pytest.raises(UserErrorException) as e:
            _client.test(flow=f"{FLOWS_DIR}/web_classification_with_invalid_additional_include")
        assert "Unable to find additional include ../invalid/file/path" in str(e.value)

    def test_pf_flow_test_with_symbolic(self, prepare_symbolic_flow):
        inputs = {"url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g", "answer": "Channel", "evidence": "Url"}
        result = _client.test(flow=f"{FLOWS_DIR}/web_classification_with_additional_include", inputs=inputs)
        assert all([key in FLOW_RESULT_KEYS for key in result])

        inputs = {"classify_with_llm.output": '{"category": "App", "evidence": "URL"}'}
        result = _client.test(flow=f"{FLOWS_DIR}/web_classification", inputs=inputs, node="convert_to_dict")
        assert all([key in FLOW_RESULT_KEYS for key in result])

    def test_pf_flow_test_with_exception(self, capsys):
        # Test flow with exception
        inputs = {"url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g", "answer": "Channel", "evidence": "Url"}
        flow_path = Path(f"{FLOWS_DIR}/web_classification_with_exception").absolute()

        with pytest.raises(UserErrorException) as exception:
            _client.test(flow=flow_path, inputs=inputs)
        assert "Execution failure in 'convert_to_dict': (Exception) mock exception" in str(exception.value)

        # Test node with exception
        inputs = {"classify_with_llm.output": '{"category": "App", "evidence": "URL"}'}
        with pytest.raises(Exception) as exception:
            _client.test(flow=flow_path, inputs=inputs, node="convert_to_dict")
        output = capsys.readouterr()
        assert "convert_to_dict.py" in output.out
        assert "mock exception" in str(exception.value)

    def test_node_test_with_connection_input(self):
        flow_path = Path(f"{FLOWS_DIR}/basic-with-connection").absolute()
        inputs = {
            "connection": "azure_open_ai_connection",
            "hello_prompt.output": "system:\n Your task is to write python program for me\nuser:\n"
            "Write a simple Hello World! program that displays "
            "the greeting message.",
        }
        result = _client.test(
            flow=flow_path,
            inputs=inputs,
            node="echo_my_prompt",
            environment_variables={"API_TYPE": "${azure_open_ai_connection.api_type}"},
        )
        assert result

    def test_pf_flow_with_aggregation(self):
        flow_path = Path(f"{FLOWS_DIR}/classification_accuracy_evaluation").absolute()
        inputs = {"variant_id": "variant_0", "groundtruth": "Pdf", "prediction": "PDF"}
        result = _client._flows._test(flow=flow_path, inputs=inputs)
        assert "calculate_accuracy" in result.node_run_infos
        assert result.run_info.metrics == {"accuracy": 1.0}

    def test_generate_tool_meta_in_additional_folder(self):
        flow_path = Path(f"{FLOWS_DIR}/web_classification_with_additional_include").absolute()
        flow_tools, _ = _client._flows._generate_tools_meta(flow=flow_path)
        for tool in flow_tools["code"].values():
            assert (Path(flow_path) / tool["source"]).exists()

    def test_pf_test_with_non_english_input(self):
        result = _client.test(flow=f"{FLOWS_DIR}/flow_with_non_english_input")
        assert result["output"] == "Hello 日本語"

    def test_pf_node_test_with_dict_input(self):
        flow_path = Path(f"{FLOWS_DIR}/flow_with_dict_input").absolute()
        flow_inputs = {"key": {"input_key": "input_value"}}
        result = _client._flows._test(flow=flow_path, inputs=flow_inputs)
        assert result.run_info.status.value == "Completed"

        inputs = {
            "get_dict_val.output.value": result.node_run_infos["get_dict_val"].output,
            "get_dict_val.output.origin_value": result.node_run_infos["get_dict_val"].output,
        }
        node_result = _client._flows._test(flow=flow_path, node="print_val", inputs=inputs)
        assert node_result.status.value == "Completed"

        inputs = {
            "val": result.node_run_infos["get_dict_val"].output,
            "origin_val": result.node_run_infos["get_dict_val"].output,
        }
        node_result = _client._flows._test(flow=flow_path, node="print_val", inputs=inputs)
        assert node_result.status.value == "Completed"

    def test_pf_node_test_with_node_ref(self):
        flow_path = Path(f"{FLOWS_DIR}/flow_with_dict_input").absolute()
        flow_inputs = {"key": {"input_key": "input_value"}}
        result = _client._flows._test(flow=flow_path, inputs=flow_inputs)
        assert result.run_info.status.value == "Completed"

        # Test node ref with reference node output names
        inputs = {
            "get_dict_val.output.value": result.node_run_infos["get_dict_val"].output["value"],
            "get_dict_val.output.origin_value": result.node_run_infos["get_dict_val"].output["origin_value"],
        }
        ref_result = _client._flows._test(flow=flow_path, node="print_val", inputs=inputs)
        assert ref_result.status.value == "Completed"

        # Test node ref with testing node input names
        inputs = {
            "val": result.node_run_infos["get_dict_val"].output["value"],
            "origin_val": result.node_run_infos["get_dict_val"].output["origin_value"],
        }
        variable_result = _client._flows._test(flow=flow_path, node="print_val", inputs=inputs)
        assert variable_result.status.value == "Completed"

    def test_pf_test_flow_in_notebook(self):
        notebook_path = Path(f"{TEST_ROOT}/test_configs/notebooks/dummy.ipynb").absolute()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_notebook_path = Path(temp_dir) / "output.ipynb"
            papermill.execute_notebook(
                notebook_path,
                output_path=output_notebook_path,
                cwd=notebook_path.parent,
            )

    def test_eager_flow_test_without_yaml(self):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/simple_without_yaml_return_output/").absolute()
        with _change_working_dir(flow_path):
            result = _client._flows.test(flow="entry:my_flow", inputs={"input_val": "val1"})
            assert result == "Hello world! val1"

    def test_class_based_eager_flow_test_without_yaml(self):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/basic_callable_class_without_yaml/").absolute()
        with _change_working_dir(flow_path):
            result = _client._flows.test(
                flow="callable_without_yaml:MyFlow", inputs={"func_input": "input"}, init={"obj_input": "val"}
            )
            assert result["func_input"] == "input"

    def test_eager_flow_test_with_yaml(self):
        clear_module_cache("entry")
        flow_path = Path(f"{EAGER_FLOWS_DIR}/simple_with_yaml/").absolute()
        result = _client._flows._test(flow=flow_path, inputs={"input_val": "val1"})
        assert result.run_info.status.value == "Completed"

    def test_eager_flow_test_with_yml(self):
        clear_module_cache("entry")
        flow_path = Path(f"{EAGER_FLOWS_DIR}/simple_with_yml/").absolute()
        result = _client._flows._test(flow=flow_path, inputs={"input_val": "val1"})
        assert result.run_info.status.value == "Completed"

    def test_eager_flow_test_with_primitive_output(self):
        clear_module_cache("entry")
        flow_path = Path(f"{EAGER_FLOWS_DIR}/primitive_output/").absolute()
        result = _client._flows._test(flow=flow_path, inputs={"input_val": "val1"})
        assert result.run_info.status.value == "Completed"

    def test_eager_flow_test_with_user_code_error(self):
        clear_module_cache("entry")
        flow_path = Path(f"{EAGER_FLOWS_DIR}/exception_in_user_code/").absolute()
        result = _client._flows._test(flow=flow_path)
        assert result.run_info.status.value == "Failed"
        assert "FlexFlowExecutionErrorDetails" in str(result.run_info.error)

    def test_eager_flow_test_invalid_cases(self):
        # wrong entry provided
        flow_path = Path(f"{EAGER_FLOWS_DIR}/incorrect_entry/").absolute()
        with pytest.raises(ValidationError) as e:
            _client._flows._test(flow=flow_path, inputs={"input_val": "val1"})
        assert "Entry function my_func is not valid." in str(e.value)

        # required inputs not provided
        clear_module_cache("entry")
        flow_path = Path(f"{EAGER_FLOWS_DIR}/required_inputs/").absolute()

        with pytest.raises(InputNotFound) as e:
            _client._flows._test(flow=flow_path)
        assert "The value for flow input 'input_val' is not provided" in str(e.value)

    def test_eager_flow_test_with_additional_includes(self):
        # in this case, flow's entry will be {EAGER_FLOWS_DIR}/flow_with_additional_includes
        # but working dir will be temp dir which includes additional included files
        clear_module_cache("flow")
        flow_path = Path(f"{EAGER_FLOWS_DIR}/flow_with_additional_includes/").absolute()
        result = _client._flows._test(flow=flow_path, inputs={"input_val": "val1"})
        assert result.run_info.status.value == "Completed", result.run_info.error

    def test_eager_flow_with_nested_entry(self):
        clear_module_cache("my_module.entry")
        flow_path = Path(f"{EAGER_FLOWS_DIR}/nested_entry/").absolute()
        result = _client._flows._test(flow=flow_path, inputs={"input_val": "val1"})
        assert result.run_info.status.value == "Completed", result.run_info.error
        assert result.output == "Hello world! val1"

    def test_eager_flow_with_environment_variables(self):
        clear_module_cache("env_var")
        flow_path = Path(f"{EAGER_FLOWS_DIR}/environment_variables/").absolute()
        result = _client._flows._test(flow=flow_path, inputs={})
        assert result.run_info.status.value == "Completed", result.run_info.error
        assert result.output == "Hello world! VAL"

    def test_eager_flow_with_evc(self):
        clear_module_cache("evc")
        flow_path = Path(f"{EAGER_FLOWS_DIR}/environment_variables_connection/").absolute()
        result = _client._flows._test(flow=flow_path, inputs={})
        assert result.run_info.status.value == "Completed", result.run_info.error
        assert result.output == "Hello world! azure"

    @pytest.mark.parametrize(
        "flow_path, expected_meta",
        [
            (
                "simple_with_yaml",
                {
                    "entry": "entry:my_flow",
                    "function": "my_flow",
                    "inputs": {"input_val": {"default": "gpt", "type": "string"}},
                },
            ),
            (
                "nested_entry",
                {
                    "entry": "my_module.entry:my_flow",
                    "function": "my_flow",
                    "inputs": {"input_val": {"default": "gpt", "type": "string"}},
                },
            ),
            (
                "flow_with_additional_includes",
                {
                    "entry": "flow:my_flow_entry",
                    "function": "my_flow_entry",
                    "inputs": {"input_val": {"default": "gpt", "type": "string"}},
                },
            ),
            (
                "basic_model_config",
                {
                    "init": {
                        "azure_open_ai_model_config": {"type": "AzureOpenAIModelConfiguration"},
                        "open_ai_model_config": {"type": "OpenAIModelConfiguration"},
                    },
                    "inputs": {"func_input": {"type": "string"}},
                    "outputs": {
                        "func_input": {"type": "string"},
                        "obj_id": {"type": "string"},
                        "obj_input": {"type": "string"},
                    },
                    "entry": "class_with_model_config:MyFlow",
                    "function": "__call__",
                },
            ),
        ],
    )
    def test_generate_flow_meta(self, flow_path, expected_meta):
        clear_module_cache("flow")
        clear_module_cache("my_module.entry")
        flow_path = Path(f"{EAGER_FLOWS_DIR}/{flow_path}").absolute()
        flow_meta = _client._flows._generate_flow_meta(flow_path)
        omitted_meta = pydash.omit(flow_meta, "environment")
        assert omitted_meta == expected_meta

    def test_generate_flow_meta_exception(self):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/incorrect_entry/").absolute()
        with pytest.raises(ValidationError) as e:
            _client._flows._generate_flow_meta(flow=flow_path)
        assert "Entry function my_func is not valid." in str(e.value)

    def test_init_executable(self):
        from promptflow.contracts.flow import FlowInputDefinition, FlowOutputDefinition

        flow_path = Path(f"{EAGER_FLOWS_DIR}/simple_with_yaml").absolute()
        executable = init_executable(flow_path=flow_path)
        # call values in executable.inputs are FlowInputDefinitions
        assert all([isinstance(value, FlowInputDefinition) for value in executable.inputs.values()])
        # call values in executable.outputs are FlowOutputDefinitions
        assert all([isinstance(value, FlowOutputDefinition) for value in executable.outputs.values()])

    def test_eager_flow_stream_output(self):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/stream_output/").absolute()
        result = _client._flows._test(flow=flow_path, inputs={})
        assert result.run_info.status.value == "Completed", result.run_info.error
        # directly return the consumed generator to align with the behavior of DAG flow test
        assert result.output == "Hello world! "

    def test_stream_output_with_builtin_llm(self):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/builtin_llm/").absolute()
        # TODO(3171565): support default value for list & dict
        result = _client._flows._test(
            flow=flow_path,
            inputs={"stream": True, "chat_history": []},
            environment_variables={
                "OPENAI_API_KEY": "${azure_open_ai_connection.api_key}",
                "AZURE_OPENAI_ENDPOINT": "${azure_open_ai_connection.api_base}",
            },
        )
        assert result.run_info.status.value == "Completed", result.run_info.error
        # directly return the consumed generator to align with the behavior of DAG flow test
        assert isinstance(result.output, str)

    def test_eager_flow_multiple_stream_outputs(self):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/multiple_stream_outputs/").absolute()
        result = _client._flows._test(flow=flow_path, inputs={})
        assert result.run_info.status.value == "Completed", result.run_info.error
        # directly return the consumed generator to align with the behavior of DAG flow test
        assert result.output == {"output1": "0123456789", "output2": "0123456789"}

    def test_eager_flow_multiple_stream_outputs_dataclass(self):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/multiple_stream_outputs_dataclass/").absolute()
        result = _client._flows._test(flow=flow_path, inputs={})
        assert result.run_info.status.value == "Completed", result.run_info.error
        # directly return the consumed generator to align with the behavior of DAG flow test
        assert is_dataclass(result.output)
        assert result.output.output1 == "0123456789"
        assert result.output.output2 == "0123456789"

    def test_flex_flow_with_init(self, pf):

        flow_path = Path(f"{EAGER_FLOWS_DIR}/basic_callable_class")
        result1 = pf.test(flow=flow_path, inputs={"func_input": "input"}, init={"obj_input": "val"})
        assert result1.func_input == "input"

        result2 = pf.test(flow=flow_path, inputs={"func_input": "input"}, init={"obj_input": "val"})
        assert result2.func_input == "input"
        assert result1.obj_id != result2.obj_id

        with pytest.raises(FlowEntryInitializationError) as ex:
            pf.test(flow=flow_path, inputs={"func_input": "input"}, init={"invalid_init_func": "val"})
        assert "got an unexpected keyword argument 'invalid_init_func'" in ex.value.message

        with pytest.raises(FlowEntryInitializationError) as ex:
            pf.test(flow=flow_path, inputs={"func_input": "input"})
        assert "__init__() missing 1 required positional argument: 'obj_input'" in ex.value.message

        with pytest.raises(InputNotFound) as ex:
            pf.test(flow=flow_path, inputs={"invalid_input_func": "input"}, init={"obj_input": "val"})
        assert "The value for flow input 'func_input' is not provided in input data" in str(ex.value)

    def test_flow_flow_with_sample(self, pf):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/basic_callable_class_with_sample_file")
        result1 = pf.test(flow=flow_path, init={"obj_input": "val"})
        assert result1.func_input == "mock_input"

        result2 = pf.test(
            flow=flow_path, init={"obj_input": "val"}, inputs=f"{EAGER_FLOWS_DIR}/basic_callable_class/inputs.jsonl"
        )
        assert result2.func_input == "func_input"

        result3 = pf.test(flow=flow_path, init={"obj_input": "val"}, inputs={"func_input": "mock_func_input"})
        assert result3.func_input == "mock_func_input"

    def test_flex_flow_with_model_config(self, pf):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/basic_model_config")
        config1 = AzureOpenAIModelConfiguration(azure_deployment="my_deployment", azure_endpoint="fake_endpoint")
        config2 = OpenAIModelConfiguration(model="my_model", base_url="fake_base_url")
        result1 = pf.test(
            flow=flow_path,
            inputs={"func_input": "input"},
            init={"azure_open_ai_model_config": config1, "open_ai_model_config": config2},
        )
        assert pydash.omit(result1, "obj_id") == {
            "azure_open_ai_model_config_azure_endpoint": "fake_endpoint",
            "azure_open_ai_model_config_connection": None,
            "azure_open_ai_model_config_deployment": "my_deployment",
            "func_input": "input",
            "open_ai_model_config_base_url": "fake_base_url",
            "open_ai_model_config_connection": None,
            "open_ai_model_config_model": "my_model",
        }

        config1 = AzureOpenAIModelConfiguration(azure_deployment="my_deployment", connection="azure_open_ai_connection")
        config2 = OpenAIModelConfiguration(model="my_model", base_url="fake_base_url")
        result2 = pf.test(
            flow=flow_path,
            inputs={"func_input": "input"},
            init={"azure_open_ai_model_config": config1, "open_ai_model_config": config2},
        )
        assert pydash.omit(result2, "obj_id", "azure_open_ai_model_config_azure_endpoint") == {
            "azure_open_ai_model_config_connection": None,
            "azure_open_ai_model_config_deployment": "my_deployment",
            "func_input": "input",
            "open_ai_model_config_base_url": "fake_base_url",
            "open_ai_model_config_connection": None,
            "open_ai_model_config_model": "my_model",
        }
        assert result1["obj_id"] != result2["obj_id"]

    def test_model_config_wrong_connection_type(self, pf):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/basic_model_config")
        config1 = AzureOpenAIModelConfiguration(azure_deployment="my_deployment", azure_endpoint="fake_endpoint")
        # using azure open ai connection to initialize open ai model config
        config2 = OpenAIModelConfiguration(model="my_model", connection="azure_open_ai_connection")
        with pytest.raises(FlowEntryInitializationError) as e:
            pf.test(
                flow=flow_path,
                inputs={"func_input": "input"},
                init={"azure_open_ai_model_config": config1, "open_ai_model_config": config2},
            )
        assert "'AzureOpenAIConnection' object has no attribute 'base_url'" in str(e.value)

    def test_yaml_default(self, pf):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/basic_with_yaml_default")
        result = pf.test(flow=flow_path, inputs={"func_input1": "input1"})
        assert result == "default_obj_input_input1_default_func_input"

        # override default input value
        result = pf.test(flow=flow_path, inputs={"func_input1": "input1", "func_input2": "input2"})
        assert result == "default_obj_input_input1_input2"

        # override default init value
        result = pf.test(
            flow=flow_path, inputs={"func_input1": "input1", "func_input2": "input2"}, init={"obj_input": "val"}
        )
        assert result == "val_input1_input2"

    def test_flow_input_parse(self, pf):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/primitive_type_inputs")
        result = pf.test(
            flow=flow_path,
            inputs={"str_input": "str", "bool_input": "True", "int_input": "1", "float_input": "1.0"},
            init={"obj_input": "val"},
        )
        assert result == {"str_output": "str", "bool_output": False, "int_output": 2, "float_output": 2.0}

        result = pf.test(
            flow=flow_path,
            inputs={"str_input": "str", "bool_input": "False", "int_input": 1, "float_input": 1.0},
            init={"obj_input": "val"},
        )
        assert result == {"str_output": "str", "bool_output": True, "int_output": 2, "float_output": 2.0}

    @pytest.mark.parametrize(
        "flow_file",
        [
            "flow.flex.yaml",
            "flow_with_sample_ref.yaml",
            "flow_with_sample_inner_ref.yaml",
        ],
    )
    def test_flow_with_sample(self, pf, flow_file):
        flow_path = Path(f"{EAGER_FLOWS_DIR}/flow_with_sample/{flow_file}")
        result = pf.test(
            flow=flow_path,
        )
        assert result == {"func_input1": "val1", "func_input2": "val2", "obj_input1": "val1", "obj_input2": "val2"}

        # when init provided, won't use it in samples
        with pytest.raises(FlowEntryInitializationError) as e:
            pf.test(
                flow=flow_path,
                init={"obj_input1": "val"},
            )
        assert "Failed to initialize flow entry with '{'obj_input1': 'val'}'" in str(e.value)

        result = pf.test(
            flow=flow_path,
            init={"obj_input1": "val", "obj_input2": "val"},
        )
        assert result == {"func_input1": "val1", "func_input2": "val2", "obj_input1": "val", "obj_input2": "val"}

        # when input provided, won't use it in samples
        with pytest.raises(InputNotFound) as e:
            pf.test(
                flow=flow_path,
                inputs={"func_input1": "input1"},
            )
        assert "The value for flow input 'func_input2' is not provided in input data." in str(e.value)

        result = pf.test(
            flow=flow_path,
            inputs={"func_input1": "val", "func_input2": "val"},
        )
        assert result == {"func_input1": "val", "func_input2": "val", "obj_input1": "val1", "obj_input2": "val2"}

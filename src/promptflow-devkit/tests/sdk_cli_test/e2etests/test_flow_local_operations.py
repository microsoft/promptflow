import copy
import os.path
import re
import shutil
import tempfile
from pathlib import Path

import mock
import pytest
from _constants import PROMPTFLOW_ROOT

from promptflow._sdk._constants import FLOW_TOOLS_JSON, NODE_VARIANTS, PROMPT_FLOW_DIR_NAME, USE_VARIANTS
from promptflow._utils.yaml_utils import load_yaml
from promptflow.connections import AzureOpenAIConnection
from promptflow.core._flow import Prompty
from promptflow.exceptions import UserErrorException

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
CONNECTION_FILE = (PROMPTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/flows"
EAGER_FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/eager_flows"
DATAS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/datas"
PROMPTY_DIR = PROMPTFLOW_ROOT / "tests/test_configs/prompty"


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
        assert os.path.isdir(f"{source}/data")
        assert not (Path(output_path) / "flow" / "data").exists()

        # check if .runs is ignored by default
        assert os.path.isfile(f"{source}/.runs/dummy_run_file")
        assert not (Path(output_path) / "flow" / ".runs" / "dummy_run_file").exists()

        # e2e_test_docker_build_and_run(output_path)

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

    def test_flow_build_flow_only(self, pf) -> None:
        source = f"{FLOWS_DIR}/web_classification_with_additional_include"
        with tempfile.TemporaryDirectory() as temp_dir:
            pf.flows.build(
                flow=source,
                output=temp_dir,
                format="docker",
                flow_only=True,
            )

            for additional_include in [
                "../external_files/convert_to_dict.py",
                "../external_files/fetch_text_content_from_url.py",
                "../external_files/summarize_text_content.jinja2",
            ]:
                additional_include_path = Path(source, additional_include)
                target_path = Path(temp_dir, additional_include_path.name)

                assert target_path.is_file()
                assert target_path.read_text() == additional_include_path.read_text()

            assert Path(temp_dir, PROMPT_FLOW_DIR_NAME, FLOW_TOOLS_JSON).is_file()

            with open(Path(temp_dir, "flow.dag.yaml"), "r", encoding="utf-8") as f:
                flow_dag_content = load_yaml(f)
                assert NODE_VARIANTS not in flow_dag_content
                assert "additional_includes" not in flow_dag_content
                assert not any([USE_VARIANTS in node for node in flow_dag_content["nodes"]])

    def test_flow_build_as_docker_with_variant(self, pf) -> None:
        source = f"{FLOWS_DIR}/web_classification_with_additional_include"
        flow_dag_path = Path(source, "flow.dag.yaml")
        flow_dag = load_yaml(flow_dag_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            pf.flows.build(
                flow=source,
                output=temp_dir,
                format="docker",
                variant="${summarize_text_content.variant_0}",
            )

            new_flow_dag_path = Path(temp_dir, "flow", "flow.dag.yaml")
            new_flow_dag = load_yaml(new_flow_dag_path)
            target_node = next(filter(lambda x: x["name"] == "summarize_text_content", new_flow_dag["nodes"]))
            target_node.pop("name")
            assert target_node == flow_dag["node_variants"]["summarize_text_content"]["variants"]["variant_0"]["node"]

    def test_flow_build_generate_flow_tools_json(self, pf) -> None:
        source = f"{FLOWS_DIR}/web_classification_with_additional_include"

        with tempfile.TemporaryDirectory() as temp_dir:
            pf.flows.build(
                flow=source,
                output=temp_dir,
                variant="${summarize_text_content.variant_0}",
            )

            flow_tools_path = Path(temp_dir) / "flow" / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON
            assert flow_tools_path.is_file()
            # package in flow.tools.json is not determined by the flow, so we don't check it here
            assert load_yaml(flow_tools_path)["code"] == {
                "classify_with_llm.jinja2": {
                    "inputs": {
                        "examples": {"type": ["string"]},
                        "text_content": {"type": ["string"]},
                        "url": {"type": ["string"]},
                    },
                    "source": "classify_with_llm.jinja2",
                    "type": "llm",
                },
                "convert_to_dict.py": {
                    "function": "convert_to_dict",
                    "inputs": {"input_str": {"type": ["string"]}},
                    "source": "convert_to_dict.py",
                    "type": "python",
                },
                "fetch_text_content_from_url.py": {
                    "function": "fetch_text_content_from_url",
                    "inputs": {"url": {"type": ["string"]}},
                    "source": "fetch_text_content_from_url.py",
                    "type": "python",
                },
                "prepare_examples.py": {
                    "function": "prepare_examples",
                    "source": "prepare_examples.py",
                    "type": "python",
                },
                "summarize_text_content.jinja2": {
                    "inputs": {"text": {"type": ["string"]}},
                    "source": "summarize_text_content.jinja2",
                    "type": "llm",
                },
            }

    def test_flow_validate_generate_flow_tools_json(self, pf) -> None:
        source = f"{FLOWS_DIR}/web_classification_with_additional_include"

        flow_tools_path = Path(source) / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON
        flow_tools_path.unlink(missing_ok=True)
        validation_result = pf.flows.validate(flow=source)

        assert validation_result.passed

        assert flow_tools_path.is_file()
        # package in flow.tools.json is not determined by the flow, so we don't check it here
        assert load_yaml(flow_tools_path)["code"] == {
            "classify_with_llm.jinja2": {
                "inputs": {
                    "examples": {"type": ["string"]},
                    "text_content": {"type": ["string"]},
                    "url": {"type": ["string"]},
                },
                "source": "classify_with_llm.jinja2",
                "type": "llm",
            },
            "convert_to_dict.py": {
                "function": "convert_to_dict",
                "inputs": {"input_str": {"type": ["string"]}},
                "source": os.path.join("..", "external_files", "convert_to_dict.py"),
                "type": "python",
            },
            "fetch_text_content_from_url.py": {
                "function": "fetch_text_content_from_url",
                "inputs": {"url": {"type": ["string"]}},
                "source": os.path.join("..", "external_files", "fetch_text_content_from_url.py"),
                "type": "python",
            },
            "prepare_examples.py": {
                "function": "prepare_examples",
                "source": "prepare_examples.py",
                "type": "python",
            },
            "summarize_text_content.jinja2": {
                "inputs": {"text": {"type": ["string"]}},
                "source": os.path.join("..", "external_files", "summarize_text_content.jinja2"),
                "type": "llm",
            },
            "summarize_text_content__variant_1.jinja2": {
                "inputs": {"text": {"type": ["string"]}},
                "source": "summarize_text_content__variant_1.jinja2",
                "type": "llm",
            },
        }

    def test_flow_validation_failed(self, pf) -> None:
        source = f"{FLOWS_DIR}/web_classification_invalid"

        flow_tools_path = Path(source) / PROMPT_FLOW_DIR_NAME / FLOW_TOOLS_JSON
        flow_tools_path.unlink(missing_ok=True)
        validation_result = pf.flows.validate(flow=source)

        error_messages = copy.deepcopy(validation_result.error_messages)
        assert "Failed to load python module from file" in error_messages.pop("nodes.2.source.path", "")
        for yaml_path in [
            "node_variants.summarize_text_content.variants.variant_0.node.source.path",
            "nodes.1.source.path",
        ]:
            assert re.search(r"Meta file '.*' can not be found.", error_messages.pop(yaml_path, ""))

        assert error_messages == {
            "inputs.url.type": "Missing data for required field.",
            "outputs.category.type": "Missing data for required field.",
        }

        assert "line 22" in repr(validation_result)

        assert flow_tools_path.is_file()
        flow_tools = load_yaml(flow_tools_path)
        assert "code" in flow_tools
        assert flow_tools["code"] == {
            "classify_with_llm.jinja2": {
                "inputs": {
                    "examples": {"type": ["string"]},
                    "text_content": {"type": ["string"]},
                    "url": {"type": ["string"]},
                },
                "source": "classify_with_llm.jinja2",
                "type": "prompt",
            },
            "./classify_with_llm.jinja2": {
                "inputs": {
                    "examples": {"type": ["string"]},
                    "text_content": {"type": ["string"]},
                    "url": {"type": ["string"]},
                },
                "source": "./classify_with_llm.jinja2",
                "type": "llm",
            },
            "convert_to_dict.py": {
                "function": "convert_to_dict",
                "inputs": {"input_str": {"type": ["string"]}},
                "source": "convert_to_dict.py",
                "type": "python",
            },
            "fetch_text_content_from_url.py": {
                "function": "fetch_text_content_from_url",
                "inputs": {"url": {"type": ["string"]}},
                "source": os.path.join("..", "external_files", "fetch_text_content_from_url.py"),
                "type": "python",
            },
            "summarize_text_content__variant_1.jinja2": {
                "inputs": {"text": {"type": ["string"]}},
                "source": "summarize_text_content__variant_1.jinja2",
                "type": "llm",
            },
        }

    def test_flow_generate_tools_meta(self, pf) -> None:
        source = f"{FLOWS_DIR}/web_classification_invalid"

        tools_meta, tools_error = pf.flows._generate_tools_meta(source)
        assert tools_meta["code"] == {
            "classify_with_llm.jinja2": {
                "inputs": {
                    "examples": {"type": ["string"]},
                    "text_content": {"type": ["string"]},
                    "url": {"type": ["string"]},
                },
                "source": "classify_with_llm.jinja2",
                "type": "prompt",
            },
            "./classify_with_llm.jinja2": {
                "inputs": {
                    "examples": {"type": ["string"]},
                    "text_content": {"type": ["string"]},
                    "url": {"type": ["string"]},
                },
                "source": "./classify_with_llm.jinja2",
                "type": "llm",
            },
            "convert_to_dict.py": {
                "function": "convert_to_dict",
                "inputs": {"input_str": {"type": ["string"]}},
                "source": "convert_to_dict.py",
                "type": "python",
            },
            "fetch_text_content_from_url.py": {
                "function": "fetch_text_content_from_url",
                "inputs": {"url": {"type": ["string"]}},
                "source": os.path.join("..", "external_files", "fetch_text_content_from_url.py"),
                "type": "python",
            },
            "summarize_text_content__variant_1.jinja2": {
                "inputs": {"text": {"type": ["string"]}},
                "source": "summarize_text_content__variant_1.jinja2",
                "type": "llm",
            },
        }
        # promptflow-tools is not installed in ci
        # assert list(tools_meta["package"]) == ["promptflow.tools.azure_translator.get_translation"]

        assert "Failed to load python module from file" in tools_error.pop("prepare_examples.py", "")
        assert re.search(r"Meta file '.*' can not be found.", tools_error.pop("summarize_text_content.jinja2", ""))
        assert tools_error == {}

        tools_meta, tools_error = pf.flows._generate_tools_meta(source, source_name="summarize_text_content.jinja2")
        assert tools_meta == {"code": {}, "package": {}}
        assert re.search(r"Meta file '.*' can not be found.", tools_error.pop("summarize_text_content.jinja2", ""))
        assert tools_error == {}

        tools_meta, tools_error = pf.flows._generate_tools_meta(source, source_name="fetch_text_content_from_url.py")
        assert tools_meta == {
            "code": {
                "fetch_text_content_from_url.py": {
                    "function": "fetch_text_content_from_url",
                    "inputs": {"url": {"type": ["string"]}},
                    "source": os.path.join("..", "external_files", "fetch_text_content_from_url.py"),
                    "type": "python",
                },
            },
            "package": {},
        }
        assert tools_error == {}

    @pytest.mark.skip(reason="It will fail in CI for some reasons. Still need to investigate.")
    def test_flow_generate_tools_meta_timeout(self, pf) -> None:
        source = f"{FLOWS_DIR}/web_classification_invalid"

        for tools_meta, tools_error in [
            pf.flows._generate_tools_meta(source, timeout=1),
            #  There is no built-in method to forcefully stop a running thread in Python
            #  because abruptly stopping a thread can cause issues like resource leaks,
            #  deadlocks, or inconsistent states.
            # Caller (VSCode extension) will handle the timeout error.
            # pf.flows._generate_tools_meta(source, source_name="convert_to_dict.py", timeout=1),
        ]:
            assert tools_meta == {"code": {}, "package": {}}
            assert tools_error
            for error in tools_error.values():
                assert "timeout" in error

    def test_flow_generate_tools_meta_with_pkg_tool_with_custom_strong_type_connection(self, pf) -> None:
        source = f"{FLOWS_DIR}/flow_with_package_tool_with_custom_strong_type_connection"

        tools_meta, tools_error = pf.flows._generate_tools_meta(source)

        assert tools_error == {}
        assert tools_meta["code"] == {}
        assert tools_meta["package"] == {
            "my_tool_package.tools.my_tool_1.my_tool": {
                "function": "my_tool",
                "inputs": {
                    "connection": {
                        "type": ["CustomConnection"],
                        "custom_type": ["MyFirstConnection", "MySecondConnection"],
                    },
                    "input_text": {"type": ["string"]},
                },
                "module": "my_tool_package.tools.my_tool_1",
                "name": "My First Tool",
                "description": "This is my first tool",
                "type": "python",
                "package": "test-custom-tools",
                "package_version": "0.0.2",
            },
            "my_tool_package.tools.my_tool_2.MyTool.my_tool": {
                "class_name": "MyTool",
                "function": "my_tool",
                "inputs": {
                    "connection": {"type": ["CustomConnection"], "custom_type": ["MySecondConnection"]},
                    "input_text": {"type": ["string"]},
                },
                "module": "my_tool_package.tools.my_tool_2",
                "name": "My Second Tool",
                "description": "This is my second tool",
                "type": "python",
                "package": "test-custom-tools",
                "package_version": "0.0.2",
            },
        }

    def test_flow_generate_tools_meta_with_script_tool_with_custom_strong_type_connection(self, pf) -> None:
        source = f"{FLOWS_DIR}/flow_with_script_tool_with_custom_strong_type_connection"

        tools_meta, tools_error = pf.flows._generate_tools_meta(source)
        assert tools_error == {}
        assert tools_meta["package"] == {}
        assert tools_meta["code"] == {
            "my_script_tool.py": {
                "function": "my_tool",
                "inputs": {
                    "connection": {"type": ["CustomConnection"]},
                    "input_param": {"type": ["string"]},
                },
                "source": "my_script_tool.py",
                "type": "python",
            }
        }

    def test_eager_flow_validate(self, pf):
        source = f"{EAGER_FLOWS_DIR}/incorrect_entry"

        validation_result = pf.flows.validate(flow=source)

        assert validation_result.error_messages == {"entry": "Entry function my_func is not valid."}
        assert "#line 1" in repr(validation_result)

        with pytest.raises(UserErrorException) as e:
            pf.flows.validate(flow=source, raise_error=True)

        assert "Entry function my_func is not valid." in str(e.value)

    def test_flow_generate_tools_meta_for_flex_flow(self, pf) -> None:
        source = f"{EAGER_FLOWS_DIR}/simple_with_yaml"

        tools_meta, tools_error = pf.flows._generate_tools_meta(source)
        assert tools_error == {}
        assert tools_meta["package"] == {}
        assert tools_meta["code"] == {}

    def test_flow_generate_tools_meta_for_prompty_flow(self, pf) -> None:
        source = f"{PROMPTY_DIR}/prompty_example.prompty"

        tools_meta, tools_error = pf.flows._generate_tools_meta(source)
        assert tools_error == {}
        assert tools_meta["package"] == {}
        assert "prompty_example.prompty" in tools_meta["code"]
        prompty = Prompty.load(source=source)
        assert all([key in tools_meta["code"]["prompty_example.prompty"]["inputs"] for key in prompty._inputs.keys()])

    def test_flow_validate_with_non_str_environment_variable(self, pf):
        source = f"{FLOWS_DIR}/flow_with_non_str_environment_variable"

        from promptflow._sdk._load_functions import load_flow

        flow = load_flow(source)
        result = flow._validate()
        assert result.passed

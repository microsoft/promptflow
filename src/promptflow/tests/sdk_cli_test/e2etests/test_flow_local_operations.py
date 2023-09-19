import copy
import os.path
import shutil
import tempfile
from pathlib import Path

import mock
import pytest
import yaml

from promptflow._sdk._constants import FLOW_TOOLS_JSON, NODE_VARIANTS, PROMPT_FLOW_DIR_NAME, USE_VARIANTS
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
                flow_dag_content = yaml.safe_load(f)
                assert NODE_VARIANTS not in flow_dag_content
                assert "additional_includes" not in flow_dag_content
                assert not any([USE_VARIANTS in node for node in flow_dag_content["nodes"]])

    def test_flow_build_as_docker_with_variant(self, pf) -> None:
        source = f"{FLOWS_DIR}/web_classification_with_additional_include"
        flow_dag_path = Path(source, "flow.dag.yaml")
        flow_dag = yaml.safe_load(flow_dag_path.read_text())

        with tempfile.TemporaryDirectory() as temp_dir:
            pf.flows.build(
                flow=source,
                output=temp_dir,
                format="docker",
                variant="${summarize_text_content.variant_0}",
            )

            new_flow_dag_path = Path(temp_dir, "flow", "flow.dag.yaml")
            new_flow_dag = yaml.safe_load(new_flow_dag_path.read_text())
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
            assert yaml.safe_load(flow_tools_path.read_text())["code"] == {
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
        assert yaml.safe_load(flow_tools_path.read_text())["code"] == {
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
            assert "Meta file not found" in error_messages.pop(yaml_path, "")

        assert error_messages == {
            "inputs.url.type": "Missing data for required field.",
            "outputs.category.type": "Missing data for required field.",
        }

        assert "line 22" in repr(validation_result)

        assert flow_tools_path.is_file()
        flow_tools = yaml.safe_load(flow_tools_path.read_text())
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
                "source": "fetch_text_content_from_url.py",
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
                "source": "fetch_text_content_from_url.py",
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
        assert "Meta file not found" in tools_error.pop("summarize_text_content.jinja2", "")
        assert tools_error == {}

        tools_meta, tools_error = pf.flows._generate_tools_meta(source, source_name="summarize_text_content.jinja2")
        assert tools_meta == {"code": {}, "package": {}}
        assert "Meta file not found" in tools_error.pop("summarize_text_content.jinja2", "")
        assert tools_error == {}

        tools_meta, tools_error = pf.flows._generate_tools_meta(source, source_name="fetch_text_content_from_url.py")
        assert tools_meta == {
            "code": {
                "fetch_text_content_from_url.py": {
                    "function": "fetch_text_content_from_url",
                    "inputs": {"url": {"type": ["string"]}},
                    "source": "fetch_text_content_from_url.py",
                    "type": "python",
                },
            },
            "package": {},
        }
        assert tools_error == {}

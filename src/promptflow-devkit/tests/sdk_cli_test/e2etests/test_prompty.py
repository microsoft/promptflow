import asyncio
import json
from pathlib import Path

import pytest
from _constants import PROMPTFLOW_ROOT
from openai.types.chat import ChatCompletion

from promptflow._sdk._pf_client import PFClient
from promptflow.core import Flow
from promptflow.core._errors import InvalidConnectionError, MissingRequiredInputError
from promptflow.core._flow import AsyncPrompty, Prompty
from promptflow.core._model_configuration import AzureOpenAIModelConfiguration
from promptflow.core._prompty_utils import convert_model_configuration_to_connection

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
DATA_DIR = TEST_ROOT / "test_configs/datas"
PROMPTY_DIR = TEST_ROOT / "test_configs/prompty"
FLOW_DIR = TEST_ROOT / "test_configs/flows"
EAGER_FLOW_DIR = TEST_ROOT / "test_configs/eager_flows"


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection", "recording_injection")
@pytest.mark.sdk_test
@pytest.mark.e2etest
class TestPrompty:
    def test_load_prompty(self):
        expect_data = {
            "name": "Basic Prompt",
            "description": "A basic prompt that uses the GPT-3 chat API to answer questions",
            "model": {
                "api": "chat",
                "configuration": {
                    "connection": "azure_open_ai_connection",
                    "azure_deployment": "gpt-35-turbo",
                    "type": "azure_openai",
                },
                "parameters": {"max_tokens": 128, "temperature": 0.2},
            },
            "inputs": {
                "firstName": {"type": "string", "default": "John"},
                "lastName": {"type": "string", "default": "Doh"},
                "question": {"type": "string"},
            },
        }
        # load prompty by flow
        prompty = Flow.load(source=f"{PROMPTY_DIR}/prompty_example.prompty")
        assert prompty._data == expect_data
        assert isinstance(prompty, Prompty)

        # load prompty by Prompty.load
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty")
        assert prompty._data == expect_data
        assert isinstance(prompty, Prompty)

        # Direct init prompty
        prompty = Prompty(path=f"{PROMPTY_DIR}/prompty_example.prompty")
        assert prompty._data == expect_data
        assert isinstance(prompty, Prompty)

    def test_overwrite_prompty(self):
        expect_data = {
            "name": "Basic Prompt",
            "description": "A basic prompt that uses the GPT-3 chat API to answer questions",
            "model": {
                "api": "chat",
                "configuration": {
                    "connection": "mock_connection_name",
                    "azure_deployment": "gpt-35-turbo",
                    "type": "azure_openai",
                },
                "parameters": {"max_tokens": 64, "temperature": 0.2, "mock_key": "mock_value"},
            },
            "inputs": {
                "firstName": {"type": "string", "default": "John"},
                "lastName": {"type": "string", "default": "Doh"},
                "question": {"type": "string"},
            },
        }
        params_override = {
            "api": "chat",
            "configuration": {"connection": "mock_connection_name"},
            "parameters": {"mock_key": "mock_value", "max_tokens": 64},
        }
        # load prompty by flow
        prompty = Flow.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model=params_override)
        assert prompty._data == expect_data
        assert isinstance(prompty, Prompty)

        # load prompty by Prompty.load
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model=params_override)
        assert prompty._data == expect_data
        assert isinstance(prompty, Prompty)

        # Direct init prompty
        prompty = Prompty(path=f"{PROMPTY_DIR}/prompty_example.prompty", model=params_override)
        assert prompty._data == expect_data
        assert isinstance(prompty, Prompty)

    def test_prompty_callable(self, pf: PFClient):
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty")
        with pytest.raises(MissingRequiredInputError) as e:
            prompty(firstName="mock_name")
        assert "Missing required inputs: ['question']" == e.value.message
        result = prompty(question="what is the result of 1+1?")
        assert "2" in result

        # Test connection with dict
        connection = convert_model_configuration_to_connection(prompty._model.configuration)
        model_dict = {
            "configuration": {
                "type": "azure_openai",
                "azure_deployment": "gpt-35-turbo",
                "api_key": connection.api_key,
                "api_version": connection.api_version,
                "azure_endpoint": connection.api_base,
                "connection": None,
            },
        }
        prompty = Flow.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model=model_dict)
        result = prompty(question="what is the result of 1+1?")
        assert "2" in result

        # Test using model configuration
        connection_obj = AzureOpenAIModelConfiguration(
            azure_endpoint=connection.api_base,
            azure_deployment="gpt-35-turbo",
            api_key=connection.api_key,
            api_version=connection.api_version,
        )
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model={"configuration": connection_obj})
        result = prompty(question="what is the result of 1+1?")
        assert "2" in result

        connection_obj = AzureOpenAIModelConfiguration(
            connection="azure_open_ai_connection",
            azure_deployment="gpt-35-turbo",
        )
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model={"configuration": connection_obj})
        result = prompty(question="what is the result of 1+1?")
        assert "2" in result

        with pytest.raises(InvalidConnectionError) as ex:
            AzureOpenAIModelConfiguration(
                azure_endpoint=connection.api_base,
                azure_deployment="gpt-35-turbo",
                api_key=connection.api_key,
                api_version=connection.api_version,
                connection="azure_open_ai_connection",
            )
        assert "Cannot configure model config and connection at the same time." in ex.value.message

        with pytest.raises(InvalidConnectionError) as ex:
            model_dict = {
                "configuration": {
                    "type": "azure_openai",
                    "azure_deployment": "gpt-35-turbo",
                    "api_key": connection.api_key,
                    "api_version": connection.api_version,
                    "azure_endpoint": connection.api_base,
                    "connection": "azure_open_ai_connection",
                },
            }
            Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model=model_dict)
        assert "Cannot configure model config and connection" in ex.value.message

        # Test format is raw
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", format="raw")
        result = prompty(question="what is the result of 1+1?")
        assert isinstance(result, ChatCompletion)

    def test_prompty_async_call(self):
        async_prompty = AsyncPrompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty")
        with pytest.raises(MissingRequiredInputError) as e:
            asyncio.run(async_prompty(firstName="mock_name"))
        assert "Missing required inputs: ['question']" == e.value.message
        result = asyncio.run(async_prompty(question="what is the result of 1+1?"))
        assert "2" in result

        # Test format is raw
        async_prompty = AsyncPrompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", format="raw")
        result = asyncio.run(async_prompty(question="what is the result of 1+1?"))
        assert isinstance(result, ChatCompletion)

    @pytest.mark.skip(reason="Failed in CI pipeline, fix it in next PR.")
    def test_prompty_batch_run(self, pf: PFClient):
        run = pf.run(flow=f"{PROMPTY_DIR}/prompty_example.prompty", data=f"{DATA_DIR}/prompty_inputs.jsonl")
        assert run.status == "Completed"
        assert "error" not in run._to_dict()

        output_data = Path(run.properties["output_path"]) / "flow_outputs" / "output.jsonl"
        with open(output_data, "r") as f:
            output = json.loads(f.readline())
            assert "2" in output["output"]

            output = json.loads(f.readline())
            assert "4" in output["output"]

            output = json.loads(f.readline())
            assert "6" in output["output"]

    def test_prompty_test(self, pf: PFClient):
        result = pf.test(
            flow=f"{PROMPTY_DIR}/prompty_example.prompty", inputs={"question": "what is the result of 1+1?"}
        )
        assert "2" in result

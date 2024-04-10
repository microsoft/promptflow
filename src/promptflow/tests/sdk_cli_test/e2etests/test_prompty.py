import asyncio
import json
from pathlib import Path

import pytest
from openai.types.chat import ChatCompletion

from promptflow._sdk._pf_client import PFClient
from promptflow.connections import AzureOpenAIConnection
from promptflow.core import Flow
from promptflow.core._errors import MissingRequiredInputError
from promptflow.core._flow import AsyncPrompty, Prompty

TEST_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = TEST_ROOT / "test_configs/datas"
PROMPTY_DIR = TEST_ROOT / "test_configs/prompty"
FLOW_DIR = TEST_ROOT / "test_configs/flows"
EAGER_FLOW_DIR = TEST_ROOT / "test_configs/eager_flows"


class TestPrompty:
    def test_load_prompty(self):
        expect_data = {
            "name": "Basic Prompt",
            "description": "A basic prompt that uses the GPT-3 chat API to answer questions",
            "model": {
                "api": "chat",
                "connection": "azure_open_ai_connection",
                "configuration": {"azure_deployment": "gpt-35-turbo", "type": "azure_openai"},
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
                "connection": "mock_connection_name",
                "configuration": {"azure_deployment": "gpt-35-turbo", "type": "azure_openai"},
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
            "connection": "mock_connection_name",
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
        connection = prompty._model.connection
        model_dict = {
            "configuration": {
                "type": "azure_openai",
                "azure_deployment": "gpt-35-turbo",
                "api_key": connection.api_key,
                "api_version": connection.api_version,
                "azure_endpoint": connection.api_base,
            },
            "connection": None,
        }
        prompty = Flow.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model=model_dict)
        result = prompty(question="what is the result of 1+1?")
        assert "2" in result

        # Test using connection object
        connection_obj = AzureOpenAIConnection(
            api_base=connection.api_base,
            api_key=connection.api_key,
        )
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model={"connection": connection_obj})
        result = prompty(question="what is the result of 1+1?")
        assert "2" in result

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

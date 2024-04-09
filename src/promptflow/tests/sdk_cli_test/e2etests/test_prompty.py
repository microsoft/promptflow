import asyncio
import json
from pathlib import Path

import pytest
from openai.types.chat import ChatCompletion

from promptflow._sdk._pf_client import PFClient
from promptflow.connections import AzureOpenAIConnection
from promptflow.core import Flow
from promptflow.core._errors import InvalidOutputKeyError, MissingRequiredInputError
from promptflow.core._flow import AsyncPrompty, Prompty

TEST_ROOT = Path(__file__).parent.parent.parent
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
                "connection": "azure_open_ai_connection",
                "parameters": {"deployment_name": "gpt-35-turbo", "max_tokens": 128, "temperature": 0.2},
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
                "parameters": {
                    "mock_key": "mock_value",
                    "deployment_name": "gpt-35-turbo",
                    "max_tokens": 64,
                    "temperature": 0.2,
                },
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
        connection = pf.connections.get(name=prompty._connection, with_secrets=True)
        connection_dict = {
            "type": connection.TYPE,
            "api_key": connection.api_key,
            "api_base": connection.api_base,
        }
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model={"connection": connection_dict})
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

    def test_prompty_async_call(self):
        async_prompty = AsyncPrompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty")
        with pytest.raises(MissingRequiredInputError) as e:
            asyncio.run(async_prompty(firstName="mock_name"))
        assert "Missing required inputs: ['question']" == e.value.message
        result = asyncio.run(async_prompty(question="what is the result of 1+1?"))
        assert "2" in result

        # Test return all choices
        async_prompty = AsyncPrompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model={"response": "all"})
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

    def test_prompty_format_output(self, pf: PFClient):
        # Test json_object format
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example_with_json_format.prompty")
        result = prompty(question="what is the result of 1+1?")
        assert isinstance(result, dict)
        assert 2 == result["answer"]
        assert "John" == result["name"]

        # Test json_object format with specified output
        prompty = Prompty.load(
            source=f"{PROMPTY_DIR}/prompty_example_with_json_format.prompty", outputs={"answer": {"type": "number"}}
        )
        result = prompty(question="what is the result of 1+1?")
        assert isinstance(result, dict)
        assert 2 == result["answer"]
        assert "name" not in result

        # Test json_object format with invalid output
        prompty = Prompty.load(
            source=f"{PROMPTY_DIR}/prompty_example_with_json_format.prompty",
            outputs={"invalid_output": {"type": "number"}},
        )
        with pytest.raises(InvalidOutputKeyError) as ex:
            prompty(question="what is the result of 1+1?")
        assert "Cannot find invalid_output in response ['name', 'answer']" in ex.value.message

        # Test stream output
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model={"parameters": {"stream": True}})
        result = prompty(question="what is the result of 1+1?")
        result_content = ""
        for item in result:
            if len(item.choices) > 0 and item.choices[0].delta.content:
                result_content += item.choices[0].delta.content
        assert "2" in result_content

        # Test return all choices
        prompty = Prompty.load(
            source=f"{PROMPTY_DIR}/prompty_example.prompty", model={"parameters": {"n": 2}, "response": "all"}
        )
        result = prompty(question="what is the result of 1+1?")
        assert isinstance(result, ChatCompletion)

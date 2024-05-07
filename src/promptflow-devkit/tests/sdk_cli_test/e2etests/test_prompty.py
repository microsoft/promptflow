import asyncio
import json
import os
import types
from pathlib import Path

import pytest
from _constants import PROMPTFLOW_ROOT
from openai import Stream
from openai.types.chat import ChatCompletion

from promptflow._sdk._pf_client import PFClient
from promptflow.client import load_flow
from promptflow.core import AsyncPrompty, Flow, Prompty
from promptflow.core._errors import (
    InvalidConnectionError,
    InvalidOutputKeyError,
    InvalidSampleError,
    MissingRequiredInputError,
)
from promptflow.core._model_configuration import AzureOpenAIModelConfiguration
from promptflow.core._prompty_utils import convert_model_configuration_to_connection
from promptflow.exceptions import UserErrorException

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

        prompty = load_flow(source=f"{PROMPTY_DIR}/prompty_example.prompty")
        result = prompty(question="what is the result of 1+1?")
        assert "2" in result

        with pytest.raises(UserErrorException) as ex:
            prompty("what is the result of 1+1?")
        assert "Prompty can only be called with keyword arguments." in ex.value.message

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
        run_dict = run._to_dict()
        assert not run_dict.get("error", None), f"error in run_dict {run_dict['error']}"

        output_data = Path(run.properties["output_path"]) / "flow_outputs" / "output.jsonl"
        with open(output_data, "r") as f:
            output = json.loads(f.readline())
            assert "2" in output["output"]

            output = json.loads(f.readline())
            assert "4" in output["output"]

            output = json.loads(f.readline())
            assert "6" in output["output"]

        # test pf run wile loaded prompty
        prompty = load_flow(source=f"{PROMPTY_DIR}/prompty_example.prompty")
        run = pf.run(flow=prompty, data=f"{DATA_DIR}/prompty_inputs.jsonl")
        assert run.status == "Completed"
        run_dict = run._to_dict()
        assert not run_dict.get("error", None), f"error in run_dict {run_dict['error']}"

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

        # Test return all choices
        prompty = Prompty.load(
            source=f"{PROMPTY_DIR}/prompty_example.prompty", model={"parameters": {"n": 2}, "response": "all"}
        )
        result = prompty(question="what is the result of 1+1?")
        assert isinstance(result, ChatCompletion)

    def test_prompty_with_stream(self, pf: PFClient):
        if pytest.is_record or pytest.is_replay:
            stream_type = types.GeneratorType
        else:
            stream_type = (types.GeneratorType, Stream)
        # Test text format with stream=true
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", model={"parameters": {"stream": True}})
        result = prompty(question="what is the result of 1+1?")
        assert isinstance(result, types.GeneratorType)
        response_contents = []
        for item in result:
            response_contents.append(item)
        assert "2" in "".join(response_contents)

        # Test text format with multi choices and response=first
        prompty = Prompty.load(
            source=f"{PROMPTY_DIR}/prompty_example.prompty", model={"parameters": {"stream": True, "n": 2}}
        )
        result = prompty(question="what is the result of 1+1?")
        assert isinstance(result, types.GeneratorType)
        response_contents = []
        for item in result:
            response_contents.append(item)
        assert "2" in "".join(response_contents)

        # Test text format with multi choices
        prompty = Prompty.load(
            source=f"{PROMPTY_DIR}/prompty_example.prompty",
            model={"parameters": {"stream": True, "n": 2}, "response": "all"},
        )
        result = prompty(question="what is the result of 1+1?")

        assert isinstance(result, stream_type)

        # Test text format with stream=true, response=all
        prompty = Prompty.load(
            source=f"{PROMPTY_DIR}/prompty_example.prompty", model={"parameters": {"stream": True}, "response": "all"}
        )
        result = prompty(question="what is the result of 1+1?")
        assert isinstance(result, stream_type)

        # Test json format with stream=true
        prompty = Prompty.load(
            source=f"{PROMPTY_DIR}/prompty_example_with_json_format.prompty",
            model={"parameters": {"n": 2, "stream": True}},
        )
        result = prompty(question="what is the result of 1+1?")
        assert isinstance(result, dict)
        assert result["answer"] == 2

        # Test json format with outputs
        prompty = Prompty.load(
            source=f"{PROMPTY_DIR}/prompty_example_with_json_format.prompty",
            model={"parameters": {"stream": True}},
            outputs={"answer": {"type": "number"}},
        )
        result = prompty(question="what is the result of 1+1?")
        assert isinstance(result, dict)
        assert list(result.keys()) == ["answer"]
        assert result["answer"] == 2

    @pytest.mark.skip(reason="Double check this test in python 3.9")
    def test_prompty_trace(self, pf: PFClient):
        run = pf.run(flow=f"{PROMPTY_DIR}/prompty_example.prompty", data=f"{DATA_DIR}/prompty_inputs.jsonl")
        line_runs = pf.traces.list_line_runs(runs=run.name)
        running_line_run = pf.traces.get_line_run(line_run_id=line_runs[0].line_run_id)
        spans = pf.traces.list_spans(trace_ids=[running_line_run.trace_id])
        prompty_span = next((span for span in spans if span.name == "Basic Prompt"), None)
        events = [pf.traces.get_event(item["attributes"]["event.id"]) for item in prompty_span.events]
        assert any(["prompt.template" in event["attributes"]["payload"] for event in events])
        assert any(["prompt.variables" in event["attributes"]["payload"] for event in events])

    def test_prompty_with_sample(self, pf: PFClient):
        prompty = Flow.load(source=f"{PROMPTY_DIR}/prompty_example_with_sample.prompty")
        result = prompty()
        assert "2" in result

        prompty = Flow.load(
            source=f"{PROMPTY_DIR}/prompty_example_with_sample.prompty", sample=f"file:{DATA_DIR}/prompty_inputs.json"
        )
        result = prompty()
        assert "2" in result

        with pytest.raises(InvalidSampleError) as ex:
            prompty = Flow.load(
                source=f"{PROMPTY_DIR}/prompty_example_with_sample.prompty", sample=f"file:{DATA_DIR}/invalid_path.json"
            )
            prompty()
        assert "Cannot find sample file" in ex.value.message

        with pytest.raises(InvalidSampleError) as ex:
            prompty = Flow.load(
                source=f"{PROMPTY_DIR}/prompty_example_with_sample.prompty",
                sample=f"file:{DATA_DIR}/prompty_inputs.jsonl",
            )
            prompty()
        assert "Only dict and json file are supported as sample in prompty" in ex.value.message

        # Test sample field as input signature
        prompty = Flow.load(source=f"{PROMPTY_DIR}/sample_as_input_signature.prompty")
        result = prompty()
        assert "2" in result

        input_signature = prompty._get_input_signature()
        assert input_signature == {
            "firstName": {"type": "string"},
            "lastName": {"type": "string"},
            "question": {"type": "string"},
        }

    def test_prompty_with_default_connection(self, pf: PFClient):
        connection = pf.connections.get(name="azure_open_ai_connection", with_secrets=True)
        os.environ["AZURE_OPENAI_ENDPOINT"] = connection.api_base
        os.environ["AZURE_OPENAI_API_KEY"] = connection.api_key
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example_with_default_connection.prompty")
        result = prompty(question="what is the result of 1+1?")
        assert "2" in result

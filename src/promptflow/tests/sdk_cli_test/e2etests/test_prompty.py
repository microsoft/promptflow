from pathlib import Path

import pytest

from promptflow._sdk._pf_client import PFClient
from promptflow.core import Flow, Prompty
from promptflow.core._errors import MissingRequiredInputError

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
            "api": "chat",
            "connection": "azure_open_ai_connection",
            "parameters": {"deployment_name": "gpt-35-turbo", "max_tokens": 128, "temperature": 0.2},
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
            "api": "chat",
            "connection": "mock_connection_name",
            "parameters": {
                "mock_key": "mock_value",
                "deployment_name": "gpt-35-turbo",
                "max_tokens": 64,
                "temperature": 0.2,
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
        prompty = Flow.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", **params_override)
        assert prompty._data == expect_data
        assert isinstance(prompty, Prompty)

        # load prompty by Prompty.load
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty", **params_override)
        assert prompty._data == expect_data
        assert isinstance(prompty, Prompty)

        # Direct init prompty
        prompty = Prompty(path=f"{PROMPTY_DIR}/prompty_example.prompty", **params_override)
        assert prompty._data == expect_data
        assert isinstance(prompty, Prompty)

    def test_prompty_callable(self):
        prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_example.prompty")
        with pytest.raises(MissingRequiredInputError) as e:
            prompty(firstName="mock_name")
        assert "Missing required inputs: ['question']" == e.value.message
        result = prompty(question="What is the meaning of life?")
        assert result

        # Test prompty with image input
        image_prompty = Prompty.load(source=f"{PROMPTY_DIR}/prompty_with_image_input.prompty")
        result = image_prompty(image_input={"data:image/png;path": ""})
        assert result

    def test_prompty_batch_run(self, pf: PFClient):
        run = pf.run(flow=f"{PROMPTY_DIR}/prompty_example.prompty", data=f"{DATA_DIR}/prompty_inputs.jsonl")
        assert run.status == "Completed"
        assert "error" not in run._to_dict()

        # Test prompty run with image
        # TODO

    def test_prompty_test(self, pf: PFClient):
        result = pf.test(flow=f"{PROMPTY_DIR}/prompty_example.prompty", inputs={"question": "what is gpt?"})
        assert result

        # Test prompty run with image
        # TODO

    def test_prompty_as_llm_node(self, pf: PFClient):
        # prompty in dag flow
        run = pf.run(flow=f"{FLOW_DIR}/flow_with_prompty", data=f"{FLOW_DIR}/flow_with_prompty/data.jsonl")
        assert run.status == "Completed"
        assert "error" not in run._to_dict()

        # prompty in eager flow
        flow_path = Path(f"{EAGER_FLOW_DIR}/flow_with_prompty")
        run = pf.run(
            flow=flow_path,
            data=f"{DATA_DIR}/simple_eager_flow_data.jsonl",
        )
        assert run.status == "Completed"
        assert "error" not in run._to_dict()

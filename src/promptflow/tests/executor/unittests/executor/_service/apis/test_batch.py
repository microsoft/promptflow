import pytest
from fastapi.testclient import TestClient

from .....utils import construct_initialization_request_json


def construct_initialize_request_json():
    return {}


@pytest.mark.unittest
class TestBatchApis:
    @pytest.mark.parametrize(
        "flow_folder, flow_file, init_kwargs, expected_inputs_definition, expected_has_aggregation",
        [
            # dag flow without aggregation nodes
            (
                "print_input_flow",
                "flow.dag.yaml",
                None,
                {
                    "text": {
                        "type": "string",
                        "default": None,
                        "description": "",
                        "enum": [],
                        "is_chat_input": False,
                        "is_chat_history": None,
                    }
                },
                False,
            ),
            # dag flow with aggregation nodes
            (
                "simple_aggregation",
                "flow.dag.yaml",
                None,
                {
                    "text": {
                        "type": "string",
                        "default": "play",
                        "description": "",
                        "enum": [],
                        "is_chat_input": False,
                        "is_chat_history": None,
                    }
                },
                True,
            ),
            # flex flow without aggregation
            (
                "simple_with_yaml",
                "flow.flex.yaml",
                None,
                {
                    "input_val": {
                        "type": "string",
                        "default": "gpt",
                        "description": None,
                        "enum": None,
                        "is_chat_input": False,
                        "is_chat_history": None,
                    }
                },
                False,
            ),
            # flex flow with aggregation
            (
                "basic_callable_class_async",
                "flow.flex.yaml",
                {"obj_input": "obj_input"},
                {
                    "func_input": {
                        "type": "string",
                        "default": None,
                        "description": None,
                        "enum": None,
                        "is_chat_input": False,
                        "is_chat_history": None,
                    }
                },
                True,
            ),
        ],
    )
    def test_initialize(
        self,
        executor_client: TestClient,
        flow_folder,
        flow_file,
        init_kwargs,
        expected_inputs_definition,
        expected_has_aggregation,
    ):
        initialization_request = construct_initialization_request_json(
            flow_folder=flow_folder,
            flow_file=flow_file,
            init_kwargs=init_kwargs,
        )
        response = executor_client.post(url="/initialize", json=initialization_request)
        # assert response
        assert response.status_code == 200
        assert response.json() == {
            "inputs_definition": expected_inputs_definition,
            "has_aggregation": expected_has_aggregation,
        }
        executor_client.post(url="/finalize")
        assert response.status_code == 200

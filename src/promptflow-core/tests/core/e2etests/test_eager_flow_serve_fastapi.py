import json

import pytest
from tests.conftest import PROMPTFLOW_ROOT

from promptflow.core._serving.utils import load_feedback_swagger
from promptflow.exceptions import UserErrorException

TEST_CONFIGS = PROMPTFLOW_ROOT / "tests" / "test_configs" / "eager_flows"


@pytest.mark.e2etest
@pytest.mark.usefixtures("recording_injection", "serving_inject_dict_provider")
class TestEagerFlowServeFastApi:
    def test_eager_flow_serve(self, fastapi_simple_eager_flow):
        response = fastapi_simple_eager_flow.post("/score", data=json.dumps({"input_val": "hi"}))
        assert (
            response.status_code == 200
        ), f"Response code indicates error {response.status_code} - {response.content.decode()}"
        response = response.json()
        assert response == {"output": "Hello world! hi"}

    def test_eager_flow_swagger(self, fastapi_simple_eager_flow):
        swagger_dict = fastapi_simple_eager_flow.get("/swagger.json").json()
        expected_swagger = {
            "components": {"securitySchemes": {"bearerAuth": {"scheme": "bearer", "type": "http"}}},
            "info": {
                "title": "Promptflow[simple_with_dict_output] API",
                "version": "1.0.0",
                "x-flow-name": "simple_with_dict_output",
            },
            "openapi": "3.0.0",
            "paths": {
                "/score": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "example": {},
                                    "schema": {
                                        "properties": {"input_val": {"default": "gpt", "type": "string"}},
                                        "required": ["input_val"],
                                        "type": "object",
                                    },
                                }
                            },
                            "description": "promptflow " "input data",
                            "required": True,
                        },
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "properties": {"output": {"type": "string"}},
                                            "type": "object",
                                        }
                                    }
                                },
                                "description": "successful " "operation",
                            },
                            "400": {"description": "Invalid " "input"},
                            "default": {"description": "unexpected " "error"},
                        },
                        "summary": "run promptflow: " "simple_with_dict_output with an " "given input",
                    }
                }
            },
            "security": [{"bearerAuth": []}],
        }
        feedback_swagger = load_feedback_swagger()
        expected_swagger["paths"]["/feedback"] = feedback_swagger
        assert swagger_dict == expected_swagger

    def test_eager_flow_serve_primitive_output(self, fastapi_simple_eager_flow_primitive_output):
        response = fastapi_simple_eager_flow_primitive_output.post("/score", data=json.dumps({"input_val": "hi"}))
        assert (
            response.status_code == 200
        ), f"Response code indicates error {response.status_code} - {response.content.decode()}"
        response = response.json()
        # response original value
        assert response == "Hello world! hi"

    def test_eager_flow_primitive_output_swagger(self, fastapi_simple_eager_flow_primitive_output):
        swagger_dict = fastapi_simple_eager_flow_primitive_output.get("/swagger.json").json()
        expected_swagger = {
            "components": {"securitySchemes": {"bearerAuth": {"scheme": "bearer", "type": "http"}}},
            "info": {
                "title": "Promptflow[primitive_output] API",
                "version": "1.0.0",
                "x-flow-name": "primitive_output",
            },
            "openapi": "3.0.0",
            "paths": {
                "/score": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "example": {},
                                    "schema": {
                                        "properties": {"input_val": {"default": "gpt", "type": "string"}},
                                        "required": ["input_val"],
                                        "type": "object",
                                    },
                                }
                            },
                            "description": "promptflow " "input data",
                            "required": True,
                        },
                        "responses": {
                            "200": {
                                "content": {"application/json": {"schema": {"type": "object"}}},
                                "description": "successful " "operation",
                            },
                            "400": {"description": "Invalid " "input"},
                            "default": {"description": "unexpected " "error"},
                        },
                        "summary": "run promptflow: primitive_output " "with an given input",
                    }
                }
            },
            "security": [{"bearerAuth": []}],
        }
        feedback_swagger = load_feedback_swagger()
        expected_swagger["paths"]["/feedback"] = feedback_swagger
        assert swagger_dict == expected_swagger

    def test_eager_flow_serve_dataclass_output(self, fastapi_simple_eager_flow_dataclass_output):
        response = fastapi_simple_eager_flow_dataclass_output.post(
            "/score", data=json.dumps({"text": "my_text", "models": ["my_model"]})
        )
        assert (
            response.status_code == 200
        ), f"Response code indicates error {response.status_code} - {response.content.decode()}"
        response = response.json()
        # response dict of dataclass
        assert response == {"models": ["my_model"], "text": "my_text"}

    def test_eager_flow_serve_non_json_serializable_output(self, mocker):
        with pytest.raises(UserErrorException, match="Parse interface for 'my_flow' failed:"):
            # instead of giving 400 response for all requests, we raise user error on serving now

            from tests.conftest import fastapi_create_client_by_model

            fastapi_create_client_by_model(
                "non_json_serializable_output",
                mocker,
                model_root=TEST_CONFIGS,
            )

    @pytest.mark.parametrize(
        "accept, expected_status_code, expected_content_type",
        [
            ("text/event-stream", 200, "text/event-stream; charset=utf-8"),
            ("text/html", 406, "application/json"),
            ("application/json", 200, "application/json"),
            ("*/*", 200, "application/json"),
            ("text/event-stream, application/json", 200, "text/event-stream; charset=utf-8"),
            ("application/json, */*", 200, "application/json"),
            ("", 200, "application/json"),
        ],
    )
    def test_eager_flow_stream_output(
        self,
        fastapi_stream_output,
        accept,
        expected_status_code,
        expected_content_type,
    ):
        payload = {
            "input_val": "val",
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": accept,
        }
        response = fastapi_stream_output.post("/score", json=payload, headers=headers)
        error_msg = f"Response code indicates error {response.status_code} - {response.content.decode()}"
        res_content_type = response.headers.get("content-type")
        assert response.status_code == expected_status_code, error_msg
        assert res_content_type == expected_content_type

        if response.status_code == 406:
            data = response.json()
            assert data["error"]["code"] == "UserError"
            assert (
                f"Media type {accept} in Accept header is not acceptable. Supported media type(s) -"
                in data["error"]["message"]
            )

        if "text/event-stream" in res_content_type:
            for line in response.content.decode().split("\n"):
                print(line)
        else:
            result = response.json()
            print(result)

    def test_eager_flow_multiple_stream_output(self, fastapi_multiple_stream_outputs):
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        response = fastapi_multiple_stream_outputs.post("/score", data=json.dumps({"input_val": 1}), headers=headers)
        assert (
            response.status_code == 400
        ), f"Response code indicates error {response.status_code} - {response.content.decode()}"
        response = response.json()
        assert response == {"error": {"code": "UserError", "message": "Multiple stream output fields not supported."}}

    def test_eager_flow_evc(self, fastapi_eager_flow_evc):
        # Supported: flow with EVC in definition
        response = fastapi_eager_flow_evc.post("/score", data=json.dumps({}))
        assert (
            response.status_code == 200
        ), f"Response code indicates error {response.status_code} - {response.content.decode()}"
        response = response.json()
        assert response == "Hello world! azure"

    def test_eager_flow_evc_override(self, fastapi_eager_flow_evc_override):
        # Supported: EVC's connection exist in flow definition
        response = fastapi_eager_flow_evc_override.post("/score", data=json.dumps({}))
        assert (
            response.status_code == 200
        ), f"Response code indicates error {response.status_code} - {response.content.decode()}"
        response = response.json()
        assert response != "Hello world! ${azure_open_ai_connection.api_base}"

    def test_eager_flow_evc_override_not_exist(self, fastapi_eager_flow_evc_override_not_exist):
        # EVC's connection not exist in flow definition, will resolve it.
        response = fastapi_eager_flow_evc_override_not_exist.post("/score", data=json.dumps({}))
        assert (
            response.status_code == 200
        ), f"Response code indicates error {response.status_code} - {response.content.decode()}"
        response = response.json()
        # EVC not resolved since the connection not exist in flow definition
        assert response == "Hello world! azure"

    def test_eager_flow_evc_connection_not_exist(self, fastapi_eager_flow_evc_connection_not_exist):
        # Won't get not existed connection since it's override
        response = fastapi_eager_flow_evc_connection_not_exist.post("/score", data=json.dumps({}))
        assert (
            response.status_code == 200
        ), f"Response code indicates error {response.status_code} - {response.content.decode()}"
        response = response.json()
        # EVC not resolved since the connection not exist in flow definition
        assert response == "Hello world! VALUE"

    def test_eager_flow_with_init(self, fastapi_callable_class):
        response1 = fastapi_callable_class.post("/score", data=json.dumps({"func_input": "input2"}))
        assert (
            response1.status_code == 200
        ), f"Response code indicates error {response1.status_code} - {response1.content.decode()}"
        response1 = response1.json()

        response2 = fastapi_callable_class.post("/score", data=json.dumps({"func_input": "input2"}))
        assert (
            response2.status_code == 200
        ), f"Response code indicates error {response2.status_code} - {response2.content.decode()}"
        response2 = response2.json()
        assert response1 == response2

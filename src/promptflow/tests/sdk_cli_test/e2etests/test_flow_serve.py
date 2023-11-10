import json
import os
import re

import pytest

from promptflow._core.operation_context import OperationContext

from ..recording_utilities import RecordStorage


@pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Doesn't support serve in replay mode")
@pytest.mark.usefixtures("flow_serving_client", "setup_local_connection")
@pytest.mark.e2etest
def test_swagger(flow_serving_client):
    swagger_dict = json.loads(flow_serving_client.get("/swagger.json").data.decode())
    assert swagger_dict == {
        "components": {"securitySchemes": {"bearerAuth": {"scheme": "bearer", "type": "http"}}},
        "info": {
            "title": "Promptflow[basic-with-connection] API",
            "version": "1.0.0",
            "x-flow-name": "basic-with-connection",
        },
        "openapi": "3.0.0",
        "paths": {
            "/score": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "example": {"text": "Hello World!"},
                                "schema": {
                                    "properties": {"text": {"type": "string"}},
                                    "required": ["text"],
                                    "type": "object",
                                },
                            }
                        },
                        "description": "promptflow input data",
                        "required": True,
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"properties": {"output_prompt": {"type": "string"}}, "type": "object"}
                                }
                            },
                            "description": "successful operation",
                        },
                        "400": {"description": "Invalid input"},
                        "default": {"description": "unexpected error"},
                    },
                    "summary": "run promptflow: basic-with-connection with an given input",
                }
            }
        },
        "security": [{"bearerAuth": []}],
    }


@pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Doesn't support serve in replay mode")
@pytest.mark.usefixtures("serving_client_llm_chat", "setup_local_connection")
@pytest.mark.e2etest
def test_chat_swagger(serving_client_llm_chat):
    swagger_dict = json.loads(serving_client_llm_chat.get("/swagger.json").data.decode())
    assert swagger_dict == {
        "components": {"securitySchemes": {"bearerAuth": {"scheme": "bearer", "type": "http"}}},
        "info": {
            "title": "Promptflow[chat_flow_with_stream_output] API",
            "version": "1.0.0",
            "x-flow-name": "chat_flow_with_stream_output",
            "x-chat-history": "chat_history",
            "x-chat-input": "question",
            "x-flow-type": "chat",
            "x-chat-output": "answer",
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
                                    "properties": {
                                        "chat_history": {
                                            "type": "array",
                                            "items": {"type": "object", "additionalProperties": {}},
                                        },
                                        "question": {"type": "string", "default": "What is ChatGPT?"},
                                    },
                                    "required": ["chat_history", "question"],
                                    "type": "object",
                                },
                            }
                        },
                        "description": "promptflow input data",
                        "required": True,
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"properties": {"answer": {"type": "string"}}, "type": "object"}
                                }
                            },
                            "description": "successful operation",
                        },
                        "400": {"description": "Invalid input"},
                        "default": {"description": "unexpected error"},
                    },
                    "summary": "run promptflow: chat_flow_with_stream_output with an given input",
                }
            }
        },
        "security": [{"bearerAuth": []}],
    }


@pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Doesn't support serve in replay mode")
@pytest.mark.usefixtures("flow_serving_client", "setup_local_connection")
@pytest.mark.e2etest
def test_user_agent(flow_serving_client):
    operation_context = OperationContext.get_instance()
    assert "test-user-agent" in operation_context.get_user_agent()
    assert "promptflow-local-serving" in operation_context.get_user_agent()


@pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Doesn't support serve in replay mode")
@pytest.mark.usefixtures("flow_serving_client", "setup_local_connection")
@pytest.mark.e2etest
def test_serving_api(flow_serving_client):
    response = flow_serving_client.get("/health")
    assert b'{"status":"Healthy","version":"0.0.1"}' in response.data
    response = flow_serving_client.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "output_prompt" in json.loads(response.data.decode())
    # Assert environment variable resolved
    assert os.environ["API_TYPE"] == "azure"


@pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Doesn't support serve in replay mode")
@pytest.mark.usefixtures("evaluation_flow_serving_client", "setup_local_connection")
@pytest.mark.e2etest
def test_evaluation_flow_serving_api(evaluation_flow_serving_client):
    response = evaluation_flow_serving_client.post("/score", data=json.dumps({"url": "https://www.microsoft.com/"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    assert "category" in json.loads(response.data.decode())


@pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Doesn't support serve in replay mode")
@pytest.mark.e2etest
def test_unknown_api(flow_serving_client):
    response = flow_serving_client.get("/unknown")
    assert b"not supported by current app" in response.data
    assert response.status_code == 404
    response = flow_serving_client.post("/health")  # health api should be GET
    assert b"not supported by current app" in response.data
    assert response.status_code == 404


@pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Doesn't support serve in replay mode")
@pytest.mark.e2etest
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
def test_stream_llm_chat(
    serving_client_llm_chat,
    accept,
    expected_status_code,
    expected_content_type,
):
    payload = {
        "question": "What is the capital of France?",
        "chat_history": [],
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": accept,
    }
    response = serving_client_llm_chat.post("/score", json=payload, headers=headers)
    assert response.status_code == expected_status_code
    assert response.content_type == expected_content_type

    if response.status_code == 406:
        assert response.json["error"]["code"] == "UserError"
        assert (
            f"Media type {accept} in Accept header is not acceptable. Supported media type(s) -"
            in response.json["error"]["message"]
        )

    if "text/event-stream" in response.content_type:
        for line in response.data.decode().split("\n"):
            print(line)
    else:
        result = response.json
        print(result)


@pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Doesn't support serve in replay mode")
@pytest.mark.e2etest
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
def test_stream_python_stream_tools(
    serving_client_python_stream_tools,
    accept,
    expected_status_code,
    expected_content_type,
):
    payload = {
        "text": "Hello World!",
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": accept,
    }
    response = serving_client_python_stream_tools.post("/score", json=payload, headers=headers)
    assert response.status_code == expected_status_code
    assert response.content_type == expected_content_type

    # The predefined flow in this test case is echo flow, which will return the input text.
    # Check output as test logic validation.
    # Stream generator generating logic
    # - The output is split into words, and each word is sent as a separate event
    # - Event data is a dict { $flowoutput_field_name : $word}
    # - The event data is formatted as f"data: {json.dumps(data)}\n\n"
    # - Generator will yield the event data for each word
    if response.status_code == 200:
        expected_output = f"Echo: {payload.get('text')}"
        if "text/event-stream" in response.content_type:
            words = expected_output.split()
            lines = response.data.decode().split("\n\n")

            # The last line is empty
            lines = lines[:-1]
            assert all(f"data: {json.dumps({'output_echo' : f'{w} '})}" == l for w, l in zip(words, lines))
        else:
            # For json response, iterator is joined into a string with "" as delimiter
            words = expected_output.split()
            merged_text = "".join(word + " " for word in words)
            expected_json = {"output_echo": merged_text}
            result = response.json
            assert expected_json == result
    elif response.status_code == 406:
        assert response.json["error"]["code"] == "UserError"
        assert (
            f"Media type {accept} in Accept header is not acceptable. Supported media type(s) -"
            in response.json["error"]["message"]
        )


@pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Doesn't support serve in replay mode")
@pytest.mark.e2etest
@pytest.mark.parametrize(
    "accept, expected_status_code, expected_content_type",
    [
        ("text/event-stream", 406, "application/json"),
        ("application/json", 200, "application/json"),
        ("*/*", 200, "application/json"),
        ("text/event-stream, application/json", 200, "application/json"),
        ("application/json, */*", 200, "application/json"),
        ("", 200, "application/json"),
    ],
)
def test_stream_python_nonstream_tools(
    flow_serving_client,
    accept,
    expected_status_code,
    expected_content_type,
):
    payload = {
        "text": "Hello World!",
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": accept,
    }
    response = flow_serving_client.post("/score", json=payload, headers=headers)
    assert response.status_code == expected_status_code
    assert response.content_type == expected_content_type

    if "text/event-stream" in response.content_type:
        for line in response.data.decode().split("\n"):
            print(line)
    else:
        result = response.json
        print(result)


@pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Doesn't support serve in replay mode")
@pytest.mark.usefixtures("serving_client_image_python_flow", "setup_local_connection")
@pytest.mark.e2etest
def test_image_flow(serving_client_image_python_flow, sample_image):
    response = serving_client_image_python_flow.post("/score", data=json.dumps({"image": sample_image}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    response = json.loads(response.data.decode())
    assert {"output"} == response.keys()
    key_regex = re.compile(r"data:image/(.*);base64")
    assert re.match(key_regex, list(response["output"].keys())[0])


@pytest.mark.skipif(RecordStorage.is_replaying_mode(), reason="Doesn't support serve in replay mode")
@pytest.mark.usefixtures("serving_client_composite_image_flow", "setup_local_connection")
@pytest.mark.e2etest
def test_list_image_flow(serving_client_composite_image_flow, sample_image):
    image_dict = {"data:image/jpg;base64": sample_image}
    response = serving_client_composite_image_flow.post(
        "/score", data=json.dumps({"image_list": [image_dict], "image_dict": {"my_image": image_dict}})
    )
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    response = json.loads(response.data.decode())
    assert {"output"} == response.keys()
    assert (
        "data:image/jpg;base64" in response["output"][0]
    ), f"data:image/jpg;base64 not in output list {response['output']}"

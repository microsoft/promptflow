import json

import pytest

from promptflow._constants import RuntimeMode
from promptflow.runtime import PromptFlowRuntime
from promptflow.runtime.serving.app import PromptflowServingApp


@pytest.mark.usefixtures("serving_client_legacy")
@pytest.mark.e2etest
def test_swagger(serving_client_legacy: PromptflowServingApp):
    swagger_dict = json.loads(serving_client_legacy.get("/swagger.json").data.decode())
    assert swagger_dict == {
        "openapi": "3.0.0",
        "info": {"title": "Promptflow[qa_with_bing] API", "version": "1.0.0"},
        "components": {"securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}}},
        "security": [{"bearerAuth": []}],
        "paths": {
            "/score": {
                "post": {
                    "summary": "run promptflow: qa_with_bing with an given input",
                    "requestBody": {
                        "description": "promptflow input data",
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"question": {"type": "string"}},
                                    "required": ["question"],
                                },
                                "example": {"question": "When did OpenAI announced their chatgpt api?"},
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "successful operation",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"answer": {"type": "object", "additionalProperties": {}}},
                                    }
                                }
                            },
                        },
                        "400": {"description": "Invalid input"},
                        "default": {"description": "unexpected error"},
                    },
                }
            }
        },
    }


@pytest.mark.usefixtures("serving_client_legacy")
@pytest.mark.e2etest
def test_serving_api_legacy(serving_client_legacy):
    response = serving_client_legacy.get("/health")
    assert b'{"status":"Healthy","version":"0.0.1"}' in response.data
    response = serving_client_legacy.post("/score", data={"question": "When did OpenAI announced their chatgpt api?"})
    assert response.status_code == 200
    assert "answer" in json.loads(response.data.decode())


@pytest.mark.usefixtures("serving_client")
@pytest.mark.e2etest
def test_serving_api(serving_client):
    response = serving_client.get("/health")
    assert b'{"status":"Healthy","version":"0.0.1"}' in response.data
    response = serving_client.post("/score", data={"text": "How are you?"})
    assert response.status_code == 200
    assert "output_prompt" in json.loads(response.data.decode())


@pytest.mark.usefixtures("serving_client_multiple_inputs")
@pytest.mark.e2etest
def test_serving_api_multiple_inputs(serving_client_multiple_inputs):
    response = serving_client_multiple_inputs.post("/score", data=b"How are you?")
    assert response.status_code == 400
    assert json.loads(response.data.decode()) == {
        "error": {
            "code": "UserError",
            "message": "Promptflow executor received non json data, but there's more than 1 input fields, "
            "please use json request data instead.",
        }
    }
    response = serving_client_multiple_inputs.post("/score", data=json.dumps({"text": "How are you?", "text2": "test"}))
    assert response.status_code == 200
    assert "output_prompt" in json.loads(response.data.decode())


@pytest.mark.usefixtures("serving_client")
@pytest.mark.e2etest
def test_runtime_mode(serving_client):
    assert serving_client is not None
    runtime = PromptFlowRuntime.get_instance()
    assert runtime.config.deployment.runtime_mode == RuntimeMode.SERVING


@pytest.mark.usefixtures("serving_client")
@pytest.mark.e2etest
def test_unknown_api(serving_client):
    response = serving_client.get("/unknown")
    assert b"not supported by current app" in response.data
    assert response.status_code == 404
    response = serving_client.post("/health")  # health api should be GET
    assert b"not supported by current app" in response.data
    assert response.status_code == 404


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
        "message": "What is the capital of France?",
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
def test_stream_llm_completion(
    serving_client_llm_completion,
    accept,
    expected_status_code,
    expected_content_type,
):
    payload = {
        "text": "I like apples, bananas and pears.",
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": accept,
    }
    response = serving_client_llm_completion.post("/score", json=payload, headers=headers)
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
    serving_client,
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
    response = serving_client.post("/score", json=payload, headers=headers)
    assert response.status_code == expected_status_code
    assert response.content_type == expected_content_type

    if "text/event-stream" in response.content_type:
        for line in response.data.decode().split("\n"):
            print(line)
    else:
        result = response.json
        print(result)


@pytest.mark.usefixtures("serving_client")
@pytest.mark.e2etest
def test_missing_required_input(serving_client):
    # Missing expected key 'text'
    response = serving_client.post("/score", data=json.dumps({"abc": "How are you?"}))
    assert response.status_code == 400
    message = json.loads(response.data.decode())["error"]["message"]
    assert "Required input fields ['text'] are missing in request data" in message

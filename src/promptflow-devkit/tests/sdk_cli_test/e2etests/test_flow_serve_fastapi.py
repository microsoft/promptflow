import json
import os
import re

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from promptflow._utils.multimedia_utils import OpenaiVisionMultimediaProcessor
from promptflow.core._serving.constants import FEEDBACK_TRACE_FIELD_NAME
from promptflow.core._serving.utils import load_feedback_swagger
from promptflow.tracing._operation_context import OperationContext


@pytest.mark.usefixtures("recording_injection", "setup_local_connection")
@pytest.mark.e2etest
def test_swagger(fastapi_flow_serving_client):
    swagger_dict = fastapi_flow_serving_client.get("/swagger.json").json()
    expected_swagger = {
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
    feedback_swagger = load_feedback_swagger()
    expected_swagger["paths"]["/feedback"] = feedback_swagger
    assert swagger_dict == expected_swagger


@pytest.mark.usefixtures("recording_injection", "setup_local_connection")
@pytest.mark.e2etest
def test_feedback_flatten(fastapi_flow_serving_client):
    resource = Resource(
        attributes={
            SERVICE_NAME: "promptflow",
        }
    )
    trace.set_tracer_provider(TracerProvider(resource=resource))
    provider = trace.get_tracer_provider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    data_field_name = "comment"
    feedback_data = {data_field_name: "positive"}
    response = fastapi_flow_serving_client.post("/feedback?flatten=true", data=json.dumps(feedback_data))
    assert response.status_code == 200
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes[data_field_name] == feedback_data[data_field_name]


@pytest.mark.usefixtures("setup_local_connection")
@pytest.mark.e2etest
def test_feedback_with_trace_context(fastapi_flow_serving_client):
    resource = Resource(
        attributes={
            SERVICE_NAME: "promptflow",
        }
    )
    trace.set_tracer_provider(TracerProvider(resource=resource))
    provider = trace.get_tracer_provider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    feedback_data = json.dumps({"feedback": "positive"})
    trace_ctx_version = "00"
    trace_ctx_trace_id = "8a3c60f7d6e2f3b4a4f2f7f3f3f3f3f3"
    trace_ctx_parent_id = "f3f3f3f3f3f3f3f3"
    trace_ctx_flags = "01"
    trace_parent = f"{trace_ctx_version}-{trace_ctx_trace_id}-{trace_ctx_parent_id}-{trace_ctx_flags}"
    response = fastapi_flow_serving_client.post(
        "/feedback", headers={"traceparent": trace_parent, "baggage": "userId=alice"}, data=feedback_data
    )
    assert response.status_code == 200
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    # validate trace context
    assert spans[0].context.trace_id == int(trace_ctx_trace_id, 16)
    assert spans[0].parent.span_id == int(trace_ctx_parent_id, 16)
    # validate feedback data
    assert feedback_data == spans[0].attributes[FEEDBACK_TRACE_FIELD_NAME]
    assert spans[0].attributes["userId"] == "alice"


@pytest.mark.usefixtures("recording_injection", "setup_local_connection")
@pytest.mark.e2etest
def test_chat_swagger(fastapi_serving_client_llm_chat):
    swagger_dict = fastapi_serving_client_llm_chat.get("/swagger.json").json()
    expected_swagger = {
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
    feedback_swagger = load_feedback_swagger()
    expected_swagger["paths"]["/feedback"] = feedback_swagger
    assert swagger_dict == expected_swagger


@pytest.mark.usefixtures("recording_injection", "setup_local_connection")
@pytest.mark.e2etest
def test_user_agent(fastapi_flow_serving_client):
    operation_context = OperationContext.get_instance()
    assert "test-user-agent" in operation_context.get_user_agent()
    assert "promptflow-local-serving" in operation_context.get_user_agent()


@pytest.mark.usefixtures("recording_injection", "setup_local_connection")
@pytest.mark.e2etest
def test_serving_api(fastapi_flow_serving_client):
    response = fastapi_flow_serving_client.get("/health")
    assert b"Healthy" in response.content
    response = fastapi_flow_serving_client.get("/")
    assert response.status_code == 200
    response = fastapi_flow_serving_client.post("/score", data=json.dumps({"text": "hi"}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.content.decode()}"
    assert "output_prompt" in response.json()
    # Assert environment variable resolved
    assert os.environ["API_TYPE"] == "azure"


@pytest.mark.usefixtures("recording_injection", "setup_local_connection")
@pytest.mark.e2etest
def test_evaluation_flow_serving_api(fastapi_evaluation_flow_serving_client):
    response = fastapi_evaluation_flow_serving_client.post(
        "/score", data=json.dumps({"url": "https://www.microsoft.com/"})
    )
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.content.decode()}"
    assert "category" in response.json()


@pytest.mark.e2etest
def test_unknown_api(fastapi_flow_serving_client):
    response = fastapi_flow_serving_client.get("/unknown")
    assert b"not supported by current app" in response.content
    assert response.status_code == 404
    response = fastapi_flow_serving_client.post("/health")  # health api should be GET
    assert b"Method Not Allowed" in response.content
    assert response.status_code == 405


@pytest.mark.usefixtures("recording_injection", "setup_local_connection")
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
    fastapi_serving_client_llm_chat,
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
    response = fastapi_serving_client_llm_chat.post("/score", json=payload, headers=headers)
    res_content_type = response.headers.get("content-type")
    assert response.status_code == expected_status_code
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
    fastapi_serving_client_python_stream_tools,
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
    response = fastapi_serving_client_python_stream_tools.post("/score", json=payload, headers=headers)
    res_content_type = response.headers.get("content-type")
    assert response.status_code == expected_status_code
    assert res_content_type == expected_content_type

    # The predefined flow in this test case is echo flow, which will return the input text.
    # Check output as test logic validation.
    # Stream generator generating logic
    # - The output is split into words, and each word is sent as a separate event
    # - Event data is a dict { $flowoutput_field_name : $word}
    # - The event data is formatted as f"data: {json.dumps(data)}\n\n"
    # - Generator will yield the event data for each word
    if response.status_code == 200:
        expected_output = f"Echo: {payload.get('text')}"
        if "text/event-stream" in res_content_type:
            words = expected_output.split()
            lines = response.content.decode().split("\n\n")

            # The last line is empty
            lines = lines[:-1]
            assert all(f"data: {json.dumps({'output_echo': f'{w} '})}" == l for w, l in zip(words, lines))
        else:
            # For json response, iterator is joined into a string with "" as delimiter
            words = expected_output.split()
            merged_text = "".join(word + " " for word in words)
            expected_json = {"output_echo": merged_text}
            result = response.json()
            assert expected_json == result
    elif response.status_code == 406:
        data = response.json()
        assert data["error"]["code"] == "UserError"
        assert (
            f"Media type {accept} in Accept header is not acceptable. Supported media type(s) -"
            in data["error"]["message"]
        )


@pytest.mark.usefixtures("recording_injection")
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
    fastapi_flow_serving_client,
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
    response = fastapi_flow_serving_client.post("/score", json=payload, headers=headers)
    res_content_type = response.headers.get("content-type")
    if "text/event-stream" in res_content_type:
        for line in response.content.decode().split("\n"):
            print(line)
    else:
        result = response.json()
        print(result)
    assert response.status_code == expected_status_code
    assert res_content_type == expected_content_type


@pytest.mark.usefixtures("recording_injection", "serving_client_image_python_flow", "setup_local_connection")
@pytest.mark.e2etest
def test_image_flow(fastapi_serving_client_image_python_flow, sample_image):
    response = fastapi_serving_client_image_python_flow.post("/score", data=json.dumps({"image": sample_image}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    response = response.json()
    assert {"output"} == response.keys()
    key_regex = re.compile(r"data:image/(.*);base64")
    assert re.match(key_regex, list(response["output"].keys())[0])


@pytest.mark.usefixtures("recording_injection", "serving_client_composite_image_flow", "setup_local_connection")
@pytest.mark.e2etest
def test_list_image_flow(fastapi_serving_client_composite_image_flow, sample_image):
    image_dict = {"data:image/jpg;base64": sample_image}
    response = fastapi_serving_client_composite_image_flow.post(
        "/score", data=json.dumps({"image_list": [image_dict], "image_dict": {"my_image": image_dict}})
    )
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    response = response.json()
    assert {"output"} == response.keys()
    assert (
        "data:image/jpg;base64" in response["output"][0]
    ), f"data:image/jpg;base64 not in output list {response['output']}"


@pytest.mark.usefixtures("recording_injection", "serving_client_openai_vision_image_flow", "setup_local_connection")
@pytest.mark.e2etest
def test_openai_vision_image_flow(fastapi_serving_client_openai_vision_image_flow, sample_image):
    response = fastapi_serving_client_openai_vision_image_flow.post("/score", data=json.dumps({"image": sample_image}))
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    response = response.json()
    assert {"output"} == response.keys()
    assert OpenaiVisionMultimediaProcessor.is_multimedia_dict(response["output"])


@pytest.mark.usefixtures("serving_client_with_environment_variables")
@pytest.mark.e2etest
def test_flow_with_environment_variables(fastapi_serving_client_with_environment_variables):
    except_environment_variables = {
        "env1": "2",
        "env2": "runtime_env2",
        "env3": "[1, 2, 3, 4, 5]",
        "env4": '{"a": 1, "b": "2"}',
        "env10": "aaaaa",
    }
    for key, value in except_environment_variables.items():
        response = fastapi_serving_client_with_environment_variables.post("/score", data=json.dumps({"key": key}))
        assert (
            response.status_code == 200
        ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
        response = response.json()
        assert {"output"} == response.keys()
        assert response["output"] == value


@pytest.mark.e2etest
def test_flow_with_async_generator(fastapi_async_generator_serving_client):
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    expected_event_num = 10
    response = fastapi_async_generator_serving_client.post(
        "/score", data=json.dumps({"count": expected_event_num}), headers=headers
    )
    assert (
        response.status_code == 200
    ), f"Response code indicates error {response.status_code} - {response.data.decode()}"
    received_event_num = 0
    for line in response.iter_lines():
        if line:
            received_event_num += 1
    assert received_event_num == expected_event_num

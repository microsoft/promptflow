import json
import os
import pytest
import sys

from pathlib import Path
from pytest_mock import MockerFixture  # noqa: E402
from tests.utils import verify_url_exists

# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import ConnectionManager
from promptflow.connections import CustomConnection, OpenAIConnection, SerpConnection, ServerlessConnection
from promptflow.contracts.multimedia import Image
from promptflow.tools.aoai import AzureOpenAI
from promptflow.tools.aoai_gpt4v import AzureOpenAI as AzureOpenAIVision

PROMPTFLOW_ROOT = Path(__file__).absolute().parents[1]
CONNECTION_FILE = (PROMPTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
root_str = str(PROMPTFLOW_ROOT.resolve().absolute())
if root_str not in sys.path:
    sys.path.insert(0, root_str)


# connection
@pytest.fixture(autouse=True)
def use_secrets_config_file(mocker: MockerFixture):
    mocker.patch.dict(os.environ, {"PROMPTFLOW_CONNECTIONS": CONNECTION_FILE})


@pytest.fixture
def azure_open_ai_connection():
    return ConnectionManager().get("azure_open_ai_connection")


@pytest.fixture
def azure_open_ai_connection_meid():
    return ConnectionManager().get("azure_open_ai_connection_meid")


@pytest.fixture
def aoai_provider(azure_open_ai_connection) -> AzureOpenAI:
    aoai_provider = AzureOpenAI(azure_open_ai_connection)
    return aoai_provider


@pytest.fixture
def aoai_vision_provider(azure_open_ai_connection) -> AzureOpenAIVision:
    aoai_provider = AzureOpenAIVision(azure_open_ai_connection)
    return aoai_provider


@pytest.fixture
def open_ai_connection():
    return ConnectionManager().get("open_ai_connection")


@pytest.fixture
def serp_connection():
    return ConnectionManager().get("serp_connection")


@pytest.fixture
def serverless_connection():
    return ConnectionManager().get("serverless_connection")


@pytest.fixture
def serverless_connection_embedding():
    return ConnectionManager().get("serverless_connection_embedding")


def verify_om_llm_custom_connection(connection: CustomConnection) -> bool:
    '''Verify that there is a MIR endpoint up and available for the Custom Connection.
    We explicitly do not pass the endpoint key to avoid the delay in generating a response.
    '''
    return verify_url_exists(connection.configs['endpoint_url'])


@pytest.fixture
def gpt2_custom_connection():
    return ConnectionManager().get("gpt2_connection")


@pytest.fixture
def open_model_llm_ws_service_connection() -> bool:
    try:
        creds_custom_connection: CustomConnection = ConnectionManager().get("open_source_llm_ws_service_connection")
        subs = json.loads(creds_custom_connection.secrets['service_credential'])
        for key, value in subs.items():
            os.environ[key] = value
        return True
    except Exception as e:
        print(f"""Something failed setting environment variables for service credentials.
Error: {e}""")
        return False


@pytest.fixture(autouse=True)
def skip_if_no_api_key(request, mocker):
    mocker.patch.dict(os.environ, {"PROMPTFLOW_CONNECTIONS": CONNECTION_FILE})
    if request.node.get_closest_marker('skip_if_no_api_key'):
        conn_name = request.node.get_closest_marker('skip_if_no_api_key').args[0]
        connection = request.getfixturevalue(conn_name)
        # if dummy placeholder key, skip.
        if isinstance(connection, OpenAIConnection) or isinstance(connection, SerpConnection) \
                or isinstance(connection, ServerlessConnection):
            if "-api-key" in connection.api_key:
                pytest.skip('skipped because no key')
        elif isinstance(connection, CustomConnection):
            if "endpoint_api_key" not in connection.secrets or "-api-key" in connection.secrets["endpoint_api_key"]:
                pytest.skip('skipped because no key')
            # Verify Custom Connections, but only those used by the Open_Model_LLM Tool
            if "endpoint_url" in connection.configs and "-endpoint-url" not in connection.configs["endpoint_url"]:
                if not verify_om_llm_custom_connection(connection):
                    pytest.skip('skipped because the connection is not valid')


# example prompts
@pytest.fixture
def example_prompt_template() -> str:
    with open(PROMPTFLOW_ROOT / "tests/test_configs/prompt_templates/marketing_writer/prompt.jinja2") as f:
        prompt_template = f.read()
    return prompt_template


@pytest.fixture
def example_prompt_template_with_name_in_roles() -> str:
    with open(PROMPTFLOW_ROOT / "tests/test_configs/prompt_templates/prompt_with_name_in_roles.jinja2") as f:
        prompt_template = f.read()
    return prompt_template


@pytest.fixture
def chat_history() -> list:
    with open(PROMPTFLOW_ROOT / "tests/test_configs/prompt_templates/marketing_writer/history.json") as f:
        history = json.load(f)
    return history


@pytest.fixture
def example_prompt_template_with_function() -> str:
    with open(PROMPTFLOW_ROOT / "tests/test_configs/prompt_templates/prompt_with_function.jinja2") as f:
        prompt_template = f.read()
    return prompt_template


@pytest.fixture
def example_prompt_template_with_tool() -> str:
    with open(PROMPTFLOW_ROOT / "tests/test_configs/prompt_templates/prompt_with_tool.jinja2") as f:
        prompt_template = f.read()
    return prompt_template


@pytest.fixture
def example_prompt_template_with_image() -> str:
    with open(PROMPTFLOW_ROOT / "tests/test_configs/prompt_templates/prompt_with_image.jinja2") as f:
        prompt_template = f.read()
    return prompt_template


@pytest.fixture
def example_image() -> Image:
    with open(PROMPTFLOW_ROOT / "tests/test_configs/prompt_templates/images/number10.jpg", "rb") as f:
        image = Image(f.read())
    return image


# functions
@pytest.fixture
def functions():
    return [
        {
            "name": "get_current_weather",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }
    ]


# tools
@pytest.fixture
def tools():
    return [
      {
        "type": "function",
        "function": {
          "name": "get_current_weather",
          "description": "Get the current weather in a given location",
          "parameters": {
            "type": "object",
            "properties": {
              "location": {
                "type": "string",
                "description": "The city and state, e.g. San Francisco, CA",
              },
              "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["location"],
          },
        }
      }
    ]


@pytest.fixture
def azure_content_safety_connection():
    return ConnectionManager().get("azure_content_safety_connection")


@pytest.fixture
def parsed_chat_with_tools():
    return [
        {
            "role": "system",
            "content": "Don't make assumptions about what values to plug into functions.",
        },
        {
            "role": "user",
            "content": "What's the weather like in San Francisco, Tokyo, and Paris?",
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_001",
                    "function": {
                        "arguments": '{"location": {"city": "San Francisco", "country": "USA"}, "unit": "metric"}',
                        "name": "get_current_weather_py",
                    },
                    "type": "function",
                },
                {
                    "id": "call_002",
                    "function": {
                        "arguments": '{"location": {"city": "Tokyo", "country": "Japan"}, "unit": "metric"}',
                        "name": "get_current_weather_py",
                    },
                    "type": "function",
                },
                {
                    "id": "call_003",
                    "function": {
                        "arguments": '{"location": {"city": "Paris", "country": "France"}, "unit": "metric"}',
                        "name": "get_current_weather_py",
                    },
                    "type": "function",
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_001",
            "content": '{"location": "San Francisco, CA", "temperature": "72", "unit": null}',
        },
        {
            "role": "tool",
            "tool_call_id": "call_002",
            "content": '{"location": "Tokyo", "temperature": "72", "unit": null}',
        },
        {
            "role": "tool",
            "tool_call_id": "call_003",
            "content": '{"location": "Paris", "temperature": "72", "unit": null}',
        },
    ]

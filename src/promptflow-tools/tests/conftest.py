import json
import os
import pytest
import sys

from pathlib import Path
from pytest_mock import MockerFixture  # noqa: E402
# Avoid circular dependencies: Use import 'from promptflow._internal' instead of 'from promptflow'
# since the code here is in promptflow namespace as well
from promptflow._internal import ConnectionManager
from promptflow.connections import CustomConnection, OpenAIConnection, SerpConnection
from promptflow.tools.aoai import AzureOpenAI

PROMOTFLOW_ROOT = Path(__file__).absolute().parents[1]
CONNECTION_FILE = (PROMOTFLOW_ROOT / "connections.json").resolve().absolute().as_posix()
root_str = str(PROMOTFLOW_ROOT.resolve().absolute())
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
def aoai_provider(azure_open_ai_connection) -> AzureOpenAI:
    aoai_provider = AzureOpenAI(azure_open_ai_connection)
    return aoai_provider


@pytest.fixture
def open_ai_connection():
    return ConnectionManager().get("open_ai_connection")


@pytest.fixture
def serp_connection():
    return ConnectionManager().get("serp_connection")


def verify_oss_llm_custom_connection(connection: CustomConnection) -> bool:
    '''Verify that there is a MIR endpoint up and available for the Custom Connection.
    We explicitly do not pass the endpoint key to avoid the delay in generating a response.
    '''

    import urllib.request
    from urllib.request import HTTPError
    from urllib.error import URLError

    try:
        urllib.request.urlopen(
            urllib.request.Request(connection.configs['endpoint_url']),
            timeout=50)
    except HTTPError as e:
        # verify that the connection is not authorized, anything else would mean the endpoint is failed
        return e.code == 403
    except URLError:
        # Endpoint does not exist - skip the test
        return False
    raise Exception("Task Succeeded unexpectedly.")


@pytest.fixture
def gpt2_custom_connection():
    return ConnectionManager().get("gpt2_connection")


@pytest.fixture
def llama_chat_custom_connection():
    return ConnectionManager().get("llama_chat_connection")


@pytest.fixture(autouse=True)
def skip_if_no_key(request, mocker):
    mocker.patch.dict(os.environ, {"PROMPTFLOW_CONNECTIONS": CONNECTION_FILE})
    if request.node.get_closest_marker('skip_if_no_key'):
        conn_name = request.node.get_closest_marker('skip_if_no_key').args[0]
        connection = request.getfixturevalue(conn_name)
        # if dummy placeholder key, skip.
        if isinstance(connection, OpenAIConnection) or isinstance(connection, SerpConnection):
            if "-api-key" in connection.api_key:
                pytest.skip('skipped because no key')
        elif isinstance(connection, CustomConnection):
            if "endpoint_api_key" not in connection.secrets or "-api-key" in connection.secrets["endpoint_api_key"]:
                pytest.skip('skipped because no key')
            # Verify Custom Connections, but only those used by the Open_Source_LLM Tool
            if "endpoint_url" in connection.configs and "-endpoint-url" not in connection.configs["endpoint_url"]:
                if not verify_oss_llm_custom_connection(connection):
                    pytest.skip('skipped because the connection is not valid')


# example prompts
@pytest.fixture
def example_prompt_template() -> str:
    with open(PROMOTFLOW_ROOT / "tests/test_configs/prompt_templates/marketing_writer/prompt.jinja2") as f:
        prompt_template = f.read()
    return prompt_template


@pytest.fixture
def chat_history() -> list:
    with open(PROMOTFLOW_ROOT / "tests/test_configs/prompt_templates/marketing_writer/history.json") as f:
        history = json.load(f)
    return history


@pytest.fixture
def example_prompt_template_with_function() -> str:
    with open(PROMOTFLOW_ROOT / "tests/test_configs/prompt_templates/prompt_with_function.jinja2") as f:
        prompt_template = f.read()
    return prompt_template


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

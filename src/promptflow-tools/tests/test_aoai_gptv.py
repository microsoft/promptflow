import pytest

from promptflow.tools.aoai_gpt4v import AzureOpenAI, ListDeploymentsError, ParseConnectionError,\
    _parse_resource_id, list_deployment_names


DEFAULT_SUBSCRIPTION_ID = "96aede12-2f73-41cb-b983-6d11a904839b"
DEFAULT_RESOURCE_GROUP_NAME = "promptflow"
DEFAULT_WORKSPACE_NAME = "promptflow-canary-dev"


@pytest.fixture
def azure_openai_provider(azure_open_ai_connection) -> AzureOpenAI:
    return AzureOpenAI(azure_open_ai_connection)


def test_parse_resource_id():
    sub = "dummy_sub"
    rg = "dummy_rg"
    account = "dummy_account"
    resource_id = (
        f"/subscriptions/{sub}/resourceGroups/{rg}/providers/"
        f"Microsoft.CognitiveServices/accounts/{account}"
    )
    parsed_sub, parsed_rg, parsed_account = _parse_resource_id(resource_id)
    assert sub == parsed_sub and rg == parsed_rg and account == parsed_account


@pytest.mark.parametrize(
        "resource_id, error_message",
        [
            ("", "Connection resourceId format invalid, cur resourceId is "),
            ("a/b/c/d", "Connection resourceId format invalid, cur resourceId is a/b/c/d"),
        ],
    )
def test_parse_resource_id_with_error(resource_id, error_message):
    with pytest.raises(ParseConnectionError, match=error_message):
        _parse_resource_id(resource_id)


@pytest.mark.parametrize(
        "connection, expected_result",
        [
            ("azure_open_ai", []),
            ("CHESI-AOAI-GPT4V", [
                {
                    'value': 'gpt-4-vision-preview',
                    'display_value': 'gpt-4-vision-preview'
                    }
                ]
            ),
        ],
    )
def test_list_deployment_names(connection, expected_result):
    res = list_deployment_names(
        DEFAULT_SUBSCRIPTION_ID,
        DEFAULT_RESOURCE_GROUP_NAME,
        DEFAULT_WORKSPACE_NAME,
        connection
    )
    assert res == expected_result


@pytest.mark.parametrize(
        "connection",
        ["mengla_test_aoai"],
    )
def test_list_deployment_names_with_error(connection):
    with pytest.raises(ListDeploymentsError) as e:
        list_deployment_names(
            DEFAULT_SUBSCRIPTION_ID,
            DEFAULT_RESOURCE_GROUP_NAME,
            DEFAULT_WORKSPACE_NAME,
            connection
        )
        assert "Failed to list deployments due to permission issue" in e.message


@pytest.mark.usefixtures("use_secrets_config_file")
@pytest.mark.skip("Skipping until we have a Azure OpenAI GPT-4 Vision deployment")
class TestAzureOpenAIGPT4V:
    def test_openai_gpt4v_chat(self, azure_openai_provider, example_prompt_template_with_image, example_image):
        result = azure_openai_provider.chat(
            prompt=example_prompt_template_with_image,
            deployment_name="gpt-4v",
            max_tokens=480,
            temperature=0,
            question="which number did you see in this picture?",
            image_input=example_image,
        )
        assert "10" == result

    def test_openai_gpt4v_stream_chat(self, azure_openai_provider, example_prompt_template_with_image, example_image):
        result = azure_openai_provider.chat(
            prompt=example_prompt_template_with_image,
            deployment_name="gpt-4v",
            max_tokens=480,
            temperature=0,
            question="which number did you see in this picture?",
            image_input=example_image,
        )
        answer = ""
        while True:
            try:
                answer += next(result)
            except Exception:
                break
        assert "10" == result

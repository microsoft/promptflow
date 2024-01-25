import pytest
from unittest.mock import patch

from azure.ai.ml._azure_environments import AzureEnvironments
from promptflow.azure.operations._arm_connection_operations import \
    ArmConnectionOperations, OpenURLFailedUserError

from promptflow.tools.aoai_gpt4v import AzureOpenAI, ListDeploymentsError, ParseConnectionError, \
    _parse_resource_id, list_deployment_names, GPT4V_VERSION


DEFAULT_SUBSCRIPTION_ID = "sub"
DEFAULT_RESOURCE_GROUP_NAME = "rg"
DEFAULT_WORKSPACE_NAME = "ws"
DEFAULT_ACCOUNT = "account"
DEFAULT_CONNECTION = "conn"


class CustomException(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


class Model:
    def __init__(self, name, version):
        self.name = name
        self.version = version


class Properties:
    def __init__(self, name, version):
        self.model = Model(name, version)


class Deployment:
    def __init__(self, name, model_name, version):
        self.name = name
        self.properties = Properties(model_name, version)


@pytest.fixture
def azure_openai_provider(azure_open_ai_connection) -> AzureOpenAI:
    return AzureOpenAI(azure_open_ai_connection)


def mock_build_connection_dict_func1(**kwargs):
    raise OpenURLFailedUserError


def mock_build_connection_dict_func2(**kwargs):
    return {"value" : {"resource_id": "abc"}}


def mock_build_connection_dict_func3(**kwargs):
    resource_id = (
        f"/subscriptions/{DEFAULT_SUBSCRIPTION_ID}/resourceGroups/{DEFAULT_RESOURCE_GROUP_NAME}"
        f"/providers/Microsoft.CognitiveServices/accounts/{DEFAULT_ACCOUNT}"
    )
    return {"value" : {"resource_id": resource_id}}


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


def test_list_deployment_names_with_conn_error(monkeypatch):
    monkeypatch.setattr(
        ArmConnectionOperations,
        "_build_connection_dict",
        mock_build_connection_dict_func1
    )
    res = list_deployment_names(
        DEFAULT_SUBSCRIPTION_ID,
        DEFAULT_RESOURCE_GROUP_NAME,
        DEFAULT_WORKSPACE_NAME,
        DEFAULT_CONNECTION
    )
    assert res == []


def test_list_deployment_names_with_wrong_connection_id(monkeypatch):
    monkeypatch.setattr(
        ArmConnectionOperations,
        "_build_connection_dict",
        mock_build_connection_dict_func2
    )
    with pytest.raises(ListDeploymentsError):
        list_deployment_names(
            DEFAULT_SUBSCRIPTION_ID,
            DEFAULT_RESOURCE_GROUP_NAME,
            DEFAULT_WORKSPACE_NAME,
            DEFAULT_CONNECTION
        )


def test_list_deployment_names_with_permission_issue(monkeypatch):
    monkeypatch.setattr(
        ArmConnectionOperations,
        "_build_connection_dict",
        mock_build_connection_dict_func3
    )
    with patch('azure.mgmt.cognitiveservices.CognitiveServicesManagementClient') as mock:
        mock.side_effect = CustomException("", 403)
        with pytest.raises(ListDeploymentsError) as excinfo:
            list_deployment_names(
                DEFAULT_SUBSCRIPTION_ID,
                DEFAULT_RESOURCE_GROUP_NAME,
                DEFAULT_WORKSPACE_NAME,
                DEFAULT_CONNECTION
            )
        assert "Failed to list deployments due to permission issue" in str(excinfo.value)


def test_list_deployment_names(monkeypatch):
    monkeypatch.setattr(
        ArmConnectionOperations,
        "_build_connection_dict",
        mock_build_connection_dict_func3
    )
    with (
        patch('azure.ai.ml._azure_environments._get_default_cloud_name') as mock_cloud_name,
        patch('azure.mgmt.cognitiveservices.CognitiveServicesManagementClient') as mock
    ):
        mock_cloud_name.return_value = AzureEnvironments.ENV_DEFAULT
        instance = mock.return_value
        instance.deployments.list.return_value = {
            Deployment("deployment1", "model1", GPT4V_VERSION),
            Deployment("deployment2", "model2", "version2")
        }
        res = list_deployment_names(
            DEFAULT_SUBSCRIPTION_ID,
            DEFAULT_RESOURCE_GROUP_NAME,
            DEFAULT_WORKSPACE_NAME,
            DEFAULT_CONNECTION
        )
        assert len(res) == 1
        assert res[0].get("value") == "deployment1"
        assert res[0].get("display_value") == "deployment1"


def test_list_deployment_names_sovereign_credential(monkeypatch):
    monkeypatch.setattr(
        ArmConnectionOperations,
        "_build_connection_dict",
        mock_build_connection_dict_func3
    )
    with (
        patch('azure.ai.ml._azure_environments._get_default_cloud_name') as mock_cloud_name,
        patch('azure.ai.ml._azure_environments._get_cloud') as mock_cloud,
        patch('azure.identity.DefaultAzureCredential') as mock_cre,
        patch('azure.mgmt.cognitiveservices.CognitiveServicesManagementClient') as mock
    ):
        mock_cloud_name.return_value = AzureEnvironments.ENV_CHINA
        cloud = mock_cloud.return_value
        cloud.get.return_value = "authority"
        mock_cre.return_value = "credential"
        instance = mock.return_value
        instance.deployments.list.return_value = {
            Deployment("deployment1", "model1", GPT4V_VERSION),
            Deployment("deployment2", "model2", "version2")
        }
        res = list_deployment_names(
            DEFAULT_SUBSCRIPTION_ID,
            DEFAULT_RESOURCE_GROUP_NAME,
            DEFAULT_WORKSPACE_NAME,
            DEFAULT_CONNECTION
        )
        assert len(res) == 1
        assert res[0].get("value") == "deployment1"
        assert res[0].get("display_value") == "deployment1"


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

import copy
import os
import pytest
import re
from azure.identity import DefaultAzureCredential
from typing import List, Dict

from promptflow.tools.exception import (
    OpenModelLLMUserError,
    OpenModelLLMKeyValidationError
)
from promptflow.tools.open_model_llm import (
    OpenModelLLM,
    API,
    ContentFormatterBase,
    LlamaContentFormatter,
    list_endpoint_names,
    list_deployment_names,
    CustomConnectionsContainer,
    get_model_type,
    ModelFamily,
    ServerlessEndpointsContainer
)


def validate_response(response):
    assert len(response) > 15


def verify_prompt_role_delimiters(message: str, codes: List[str]):
    assert codes == "UserError/OpenModelLLMUserError".split("/")

    message_pattern = re.compile(
        r"The Chat API requires a specific format for prompt definition, and the prompt should include separate "
        + r"lines as role delimiters: ('(assistant|user|system):\\n'[,.]){3} Current parsed role 'the quick brown"
        + r" fox' does not meet the requirement. If you intend to use the "
        + r"Completion API, please select the appropriate API type and deployment name. If you do intend to use the "
        + r"Chat API, please refer to the guideline at https://aka.ms/pfdoc/chat-prompt or view the samples in our "
        + r"gallery that contain 'Chat' in the name.")
    is_match = message_pattern.match(message)
    assert is_match


@pytest.fixture
def verify_service_endpoints(open_model_llm_ws_service_connection) -> Dict[str, List[str]]:
    if not open_model_llm_ws_service_connection:
        pytest.skip("Service Credential not available")
    print("open_model_llm_ws_service_connection completed")
    required_env_vars = ["AZUREML_ARM_SUBSCRIPTION", "AZUREML_ARM_RESOURCEGROUP", "AZUREML_ARM_WORKSPACE_NAME",
                         "AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_CLIENT_SECRET"]
    for rev in required_env_vars:
        if rev not in os.environ:
            raise Exception(f"test not setup correctly. Missing Required Environment Variable:{rev}")


@pytest.fixture
def endpoints_provider(verify_service_endpoints) -> Dict[str, List[str]]:
    from azure.ai.ml import MLClient
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    ml_client = MLClient(
        credential=credential,
        subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
        resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
        workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"))

    endpoints = {}
    for ep in ml_client.online_endpoints.list():
        endpoints[ep.name] = [d.name for d in ml_client.online_deployments.list(ep.name)]

    return endpoints


@pytest.fixture
def chat_endpoints_provider(endpoints_provider: Dict[str, List[str]]) -> Dict[str, List[str]]:
    chat_endpoint_names = ["gpt2", "llama-chat"]

    chat_endpoints = {}
    for key, value in endpoints_provider.items():
        for ep_name in chat_endpoint_names:
            if ep_name in key:
                chat_endpoints[key] = value

    if len(chat_endpoints) <= 0:
        pytest.skip("No Chat Endpoints Found")

    return chat_endpoints


@pytest.fixture
def completion_endpoints_provider(endpoints_provider: Dict[str, List[str]]) -> Dict[str, List[str]]:
    completion_endpoint_names = ["gpt2", "llama-comp"]

    completion_endpoints = {}
    for key, value in endpoints_provider.items():
        for ep_name in completion_endpoint_names:
            if ep_name in key:
                completion_endpoints[key] = value

    if len(completion_endpoints) <= 0:
        pytest.skip("No Completion Endpoints Found")

    return completion_endpoints


@pytest.mark.skip("Skipping - requires new test resources")
@pytest.mark.usefixtures("use_secrets_config_file")
class TestOpenModelLLM:
    stateless_os_llm = OpenModelLLM()
    gpt2_connection = "connection/gpt2_connection"
    llama_connection = "connection/llama_chat_connection"
    llama_serverless_connection = "connection/llama_chat_serverless"
    completion_prompt = "The quick brown fox"
    chat_prompt = """system:
* You are a AI which helps Customers complete a sentence.
* Your answer should complete the provided prompt.
* Your answer should be followed by a discussion of the meaning.
* The discussion part of your answer must be long and detailed.

user:
""" + completion_prompt

    def test_open_model_llm_completion(self, verify_service_endpoints):
        response = self.stateless_os_llm.call(
            self.completion_prompt,
            API.COMPLETION,
            endpoint_name=self.gpt2_connection)
        validate_response(response)

    def test_open_model_llm_completion_with_deploy(self, verify_service_endpoints):
        response = self.stateless_os_llm.call(
            self.completion_prompt,
            API.COMPLETION,
            endpoint_name=self.gpt2_connection,
            deployment_name="gpt2-10")
        validate_response(response)

    def test_open_model_llm_chat(self, verify_service_endpoints):
        response = self.stateless_os_llm.call(
            self.chat_prompt,
            API.CHAT,
            endpoint_name=self.gpt2_connection)
        validate_response(response)

    def test_open_model_llm_chat_with_deploy(self, verify_service_endpoints):
        response = self.stateless_os_llm.call(
            self.chat_prompt,
            API.CHAT,
            endpoint_name=self.gpt2_connection,
            deployment_name="gpt2-10")
        validate_response(response)

    def test_open_model_llm_chat_with_max_length(self, verify_service_endpoints):
        response = self.stateless_os_llm.call(
            self.chat_prompt,
            API.CHAT,
            endpoint_name=self.gpt2_connection,
            max_new_tokens=30)
        # GPT-2 doesn't take this parameter
        validate_response(response)

    @pytest.mark.skip_if_no_api_key("gpt2_custom_connection")
    def test_open_model_llm_con_url_chat(self, gpt2_custom_connection):
        tmp = copy.deepcopy(gpt2_custom_connection)
        del tmp.configs['endpoint_url']
        with pytest.raises(OpenModelLLMKeyValidationError) as exc_info:
            customConnectionsContainer = CustomConnectionsContainer()
            customConnectionsContainer.get_endpoint_from_custom_connection(connection=tmp)
        assert exc_info.value.message == """Required key `endpoint_url` not found in given custom connection.
Required keys are: endpoint_url,model_family."""
        assert exc_info.value.error_codes == "UserError/ToolValidationError/OpenModelLLMKeyValidationError".split("/")

    @pytest.mark.skip_if_no_api_key("gpt2_custom_connection")
    def test_open_model_llm_con_key_chat(self, gpt2_custom_connection):
        tmp = copy.deepcopy(gpt2_custom_connection)
        del tmp.secrets['endpoint_api_key']
        with pytest.raises(OpenModelLLMKeyValidationError) as exc_info:
            customConnectionsContainer = CustomConnectionsContainer()
            customConnectionsContainer.get_endpoint_from_custom_connection(connection=tmp)
        assert exc_info.value.message == (
            "Required secret key `endpoint_api_key` "
            + """not found in given custom connection.
Required keys are: endpoint_api_key.""")
        assert exc_info.value.error_codes == "UserError/ToolValidationError/OpenModelLLMKeyValidationError".split("/")

    @pytest.mark.skip_if_no_api_key("gpt2_custom_connection")
    def test_open_model_llm_con_model_chat(self, gpt2_custom_connection):
        tmp = copy.deepcopy(gpt2_custom_connection)
        del tmp.configs['model_family']
        with pytest.raises(OpenModelLLMKeyValidationError) as exc_info:
            customConnectionsContainer = CustomConnectionsContainer()
            customConnectionsContainer.get_endpoint_from_custom_connection(connection=tmp)
        assert exc_info.value.message == """Required key `model_family` not found in given custom connection.
Required keys are: endpoint_url,model_family."""
        assert exc_info.value.error_codes == "UserError/ToolValidationError/OpenModelLLMKeyValidationError".split("/")

    def test_open_model_llm_escape_chat(self):
        danger = r"The quick \brown fox\tjumped\\over \the \\boy\r\n"
        out_of_danger = ContentFormatterBase.escape_special_characters(danger)
        assert out_of_danger == "The quick \\brown fox\\tjumped\\\\over \\the \\\\boy\\r\\n"

    def test_open_model_llm_llama_parse_chat_with_chat(self):
        LlamaContentFormatter.parse_chat(self.chat_prompt)

    def test_open_model_llm_llama_parse_multi_turn(self):
        multi_turn_chat = """user:
You are a AI which helps Customers answer questions.

What is the best movie of all time?

assistant:
Mobius, which starred Jared Leto

user:
Why was that the greatest movie of all time?
"""
        LlamaContentFormatter.parse_chat(multi_turn_chat)

    def test_open_model_llm_llama_parse_ignore_whitespace(self):
        bad_chat_prompt = f"""system:
You are a AI which helps Customers answer questions.

user:

user:
{self.completion_prompt}"""
        with pytest.raises(OpenModelLLMUserError) as exc_info:
            LlamaContentFormatter.parse_chat(bad_chat_prompt)
        verify_prompt_role_delimiters(exc_info.value.message, exc_info.value.error_codes)

    def test_open_model_llm_llama_parse_chat_with_comp(self):
        with pytest.raises(OpenModelLLMUserError) as exc_info:
            LlamaContentFormatter.parse_chat(self.completion_prompt)
        verify_prompt_role_delimiters(exc_info.value.message, exc_info.value.error_codes)

    def test_open_model_llm_chat_endpoint_name(self, chat_endpoints_provider):
        for endpoint_name in chat_endpoints_provider:
            response = self.stateless_os_llm.call(
                self.chat_prompt,
                API.CHAT,
                endpoint_name=f"onlineEndpoint/{endpoint_name}")
            validate_response(response)

    def test_open_model_llm_chat_endpoint_name_with_deployment(self, chat_endpoints_provider):
        for endpoint_name in chat_endpoints_provider:
            for deployment_name in chat_endpoints_provider[endpoint_name]:
                response = self.stateless_os_llm.call(
                    self.chat_prompt,
                    API.CHAT,
                    endpoint_name=f"onlineEndpoint/{endpoint_name}",
                    deployment_name=deployment_name)
                validate_response(response)

    def test_open_model_llm_completion_endpoint_name(self, completion_endpoints_provider):
        for endpoint_name in completion_endpoints_provider:
            response = self.stateless_os_llm.call(
                self.completion_prompt,
                API.COMPLETION,
                endpoint_name=f"onlineEndpoint/{endpoint_name}")
            validate_response(response)

    def test_open_model_llm_completion_endpoint_name_with_deployment(self, completion_endpoints_provider):
        for endpoint_name in completion_endpoints_provider:
            for deployment_name in completion_endpoints_provider[endpoint_name]:
                response = self.stateless_os_llm.call(
                    self.completion_prompt,
                    API.COMPLETION,
                    endpoint_name=f"onlineEndpoint/{endpoint_name}",
                    deployment_name=deployment_name)
                validate_response(response)

    def test_open_model_llm_llama_chat(self, verify_service_endpoints):
        response = self.stateless_os_llm.call(self.chat_prompt, API.CHAT, endpoint_name=self.llama_connection)
        validate_response(response)

    def test_open_model_llm_llama_serverless(self, verify_service_endpoints):
        response = self.stateless_os_llm.call(
            self.chat_prompt,
            API.CHAT,
            endpoint_name=self.llama_serverless_connection)
        validate_response(response)

    def test_open_model_llm_llama_chat_history(self, verify_service_endpoints):
        chat_history_prompt = """system:
* Given the following conversation history and the users next question, answer the next question.
* If the conversation is irrelevant or empty, acknowledge and ask for more input.
* Do not add more details than necessary to the question.

chat history:
{% for item in chat_history %}
user:
{{ item.inputs.chat_input }}

assistant:
{{ item.outputs.chat_output }}
{% endfor %}

user:
{{ chat_input }}"""
        response = self.stateless_os_llm.call(
            chat_history_prompt,
            API.CHAT,
            endpoint_name=self.llama_connection,
            chat_history=[
                {
                    "inputs":
                    {
                        "chat_input": "Hi"
                    },
                    "outputs":
                    {
                        "chat_output": "Hello! How can I assist you today?"
                    }
                },
                {
                    "inputs":
                    {
                        "chat_input": "What is Azure compute instance?"
                    },
                    "outputs":
                    {
                        "chat_output": "An Azure Machine Learning compute instance is a fully managed cloud-based"
                        + " workstation for data scientists. It provides a pre-configured and managed development"
                        + " environment in the cloud for machine learning. Compute instances can also be used as a"
                        + " compute target for training and inferencing for development and testing purposes. They"
                        + " have a job queue, run jobs securely in a virtual network environment, and can run"
                        + " multiple small jobs in parallel. Additionally, compute instances support single-node"
                        + " multi-GPU distributed training jobs."
                    }
                }
            ],
            chat_input="Sorry I didn't follow, could you say that again?")
        validate_response(response)

    def test_open_model_llm_dynamic_list_ignore_deployment(self, verify_service_endpoints):
        deployments = list_deployment_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            endpoint=None)
        assert len(deployments) == 1
        assert deployments[0]['value'] == 'default'

        deployments = list_deployment_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            endpoint='')
        assert len(deployments) == 1
        assert deployments[0]['value'] == 'default'

        deployments = list_deployment_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            endpoint='fake_endpoint name')
        assert len(deployments) == 1
        assert deployments[0]['value'] == 'default'

    def test_open_model_llm_dynamic_list_serverless_test(self, verify_service_endpoints):
        subscription_id = os.getenv("AZUREML_ARM_SUBSCRIPTION")
        resource_group_name = os.getenv("AZUREML_ARM_RESOURCEGROUP")
        workspace_name = os.getenv("AZUREML_ARM_WORKSPACE_NAME")

        se_container = ServerlessEndpointsContainer()
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        token = credential.get_token("https://management.azure.com/.default").token

        eps = se_container.list_serverless_endpoints(
            token,
            subscription_id,
            resource_group_name,
            workspace_name)

        if len(eps) == 0:
            pytest.skip("Service Credential not available")

        endpoint_connection_name = eps[0]["value"].replace("serverlessEndpoint/", "")

        eps_keys = se_container._list_endpoint_key(
            token,
            subscription_id,
            resource_group_name,
            workspace_name,
            endpoint_connection_name
        )
        assert len(eps_keys) == 2

        (endpoint_url, endpoint_key, model_family) = se_container.get_serverless_endpoint_key(
            token,
            subscription_id,
            resource_group_name,
            workspace_name,
            endpoint_connection_name)

        assert len(endpoint_url) > 20
        assert model_family == "LLaMa"
        assert endpoint_key == eps_keys['primaryKey']

    def test_open_model_llm_dynamic_list_custom_connections_test(self, verify_service_endpoints):
        custom_container = CustomConnectionsContainer()
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)

        connections = custom_container.list_custom_connection_names(
            credential,
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"))
        assert len(connections) > 1

    def test_open_model_llm_dynamic_list_happy_path(self, verify_service_endpoints):
        endpoints = list_endpoint_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            return_endpoint_url=True
            )
        # we might want to remove this or skip if there are zero endpoints in the long term.
        # currently we have low cost compute for a GPT2 endpoint, so if nothing else this should be available.
        assert len(endpoints) > 0
        for endpoint in endpoints:
            assert "value" in endpoint
            assert "display_value" in endpoint
            assert "description" in endpoint

        from tests.utils import verify_url_exists
        for endpoint in endpoints:
            if "localConnection/" in endpoint['value'] or not verify_url_exists(endpoint["url"]):
                continue

            is_chat = "serverless" in endpoint['value'] or "chat" in endpoint['value']

            if is_chat:
                prompt = self.chat_prompt
                api_type = API.CHAT
            else:
                prompt = self.completion_prompt
                api_type = API.COMPLETION

            # test with default endpoint
            response = self.stateless_os_llm.call(
                prompt,
                api_type,
                endpoint_name=endpoint['value'],
                max_new_tokens=30,
                model_kwargs={})
            validate_response(response)

            deployments = list_deployment_names(
                subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
                resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
                workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
                endpoint=endpoint['value'])
            if "onlineEndpoint" in endpoint['value']:
                assert len(deployments) > 0
            else:
                assert len(deployments) == 1
                assert deployments[0]['value'] == 'default'
                continue

            for deployment in deployments:
                response = self.stateless_os_llm.call(
                    prompt,
                    api_type,
                    endpoint_name=endpoint['value'],
                    deployment_name=deployment['value'],
                    max_new_tokens=30,
                    model_kwargs={})
                validate_response(response)

    def test_open_model_llm_get_model_llama(self):
        model_assets = [
            "azureml://registries/azureml-meta/models/Llama-2-7b-chat/versions/14",
            "azureml://registries/azureml-meta/models/Llama-2-7b/versions/12",
            "azureml://registries/azureml-meta/models/Llama-2-13b-chat/versions/12",
            "azureml://registries/azureml-meta/models/Llama-2-13b/versions/12",
            "azureml://registries/azureml-meta/models/Llama-2-70b-chat/versions/12",
            "azureml://registries/azureml-meta/models/Llama-2-70b/versions/13"
        ]

        for asset_name in model_assets:
            assert ModelFamily.LLAMA == get_model_type(asset_name)

    def test_open_model_llm_get_model_gpt2(self):
        model_assets = [
            "azureml://registries/azureml-staging/models/gpt2/versions/9",
            "azureml://registries/azureml/models/gpt2/versions/9",
            "azureml://registries/azureml/models/gpt2-medium/versions/11",
            "azureml://registries/azureml/models/gpt2-large/versions/11"
        ]

        for asset_name in model_assets:
            assert ModelFamily.GPT2 == get_model_type(asset_name)

    def test_open_model_llm_get_model_dolly(self):
        model_assets = [
            "azureml://registries/azureml/models/databricks-dolly-v2-12b/versions/11"
        ]

        for asset_name in model_assets:
            assert ModelFamily.DOLLY == get_model_type(asset_name)

    def test_open_model_llm_get_model_falcon(self):
        model_assets = [
            "azureml://registries/azureml/models/tiiuae-falcon-40b/versions/2",
            "azureml://registries/azureml/models/tiiuae-falcon-40b/versions/2"
        ]

        for asset_name in model_assets:
            assert ModelFamily.FALCON == get_model_type(asset_name)

    def test_open_model_llm_get_model_failure_cases(self):
        bad_model_assets = [
            "azureml://registries/azureml-meta/models/CodeLlama-7b-Instruct-hf/versions/3",
            "azureml://registries/azureml-staging/models/gpt-2/versions/9",
            "azureml://registries/azureml/models/falcon-40b/versions/2",
            "azureml://registries/azureml-meta/models/Llama-70b/versions/13",
            "azureml://registries/azureml/models/openai-whisper-large/versions/14",
            "azureml://registries/azureml/models/ask-wikipedia/versions/2",
            "definitely not real",
            "",
            "ausreml://registries/azureml/models/ask-wikipedia/versions/2",
            "azureml://registries/azureml/models/ask-wikipedia/version/2",
            "azureml://registries/azureml/models/ask-wikipedia/version/"
        ]

        for asset_name in bad_model_assets:
            val = get_model_type(asset_name)
            assert val is None

    def test_open_model_llm_local_connection(self, verify_service_endpoints, gpt2_custom_connection):
        endpoints = list_endpoint_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            return_endpoint_url=True
            )

        import uuid
        connection_name = f"test_local_connection_{uuid.uuid4()}"

        for e in endpoints:
            assert e['value'] != connection_name

        from promptflow._sdk.entities import CustomConnection
        connection = CustomConnection(name=connection_name,
                                      configs={
                                          "endpoint_url": gpt2_custom_connection.configs['endpoint_url'],
                                          "model_family": gpt2_custom_connection.configs['model_family']},
                                      secrets={
                                          "endpoint_api_key": gpt2_custom_connection.secrets['endpoint_api_key']})

        from promptflow import PFClient as LocalPFClient
        pf_client = LocalPFClient()
        pf_client.connections.create_or_update(connection)

        endpoints = list_endpoint_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            force_refresh=True
            )

        found = False
        target_connection_name = f"localConnection/{connection_name}"
        for e in endpoints:
            if e['value'] == target_connection_name:
                found = True
                break
        assert found

        response = self.stateless_os_llm.call(
            self.completion_prompt,
            API.COMPLETION,
            endpoint_name=target_connection_name)
        validate_response(response)

    def test_open_model_llm_package(self):
        import pkg_resources
        # Promptflow-tools is not installed in the test pipeline, so we'll skip this test there. Works locally.
        try:
            pkg_resources.get_distribution("promptflow-tools")
        except pkg_resources.DistributionNotFound:
            pytest.skip("promptflow-tools not installed")

        found = False
        target_tool_identifier = "promptflow.tools.open_model_llm.OpenModelLLM.call"
        for entry_point in pkg_resources.iter_entry_points(group="package_tools"):
            list_tool_func = entry_point.resolve()
            package_tools = list_tool_func()

            for identifier, tool in package_tools.items():
                if identifier == target_tool_identifier:
                    import importlib
                    importlib.import_module(tool["module"])  # Import the module to ensure its validity
                    assert not found
                    found = True
        assert found

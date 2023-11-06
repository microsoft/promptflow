import copy
import os
import pytest
from typing import List, Dict

from typing import List, Dict

from promptflow.tools.exception import (
    OpenSourceLLMUserError,
    OpenSourceLLMKeyValidationError
)
from promptflow.tools.open_source_llm import (
    OpenSourceLLM,
    API,
    ContentFormatterBase,
    LlamaContentFormatter,
    list_endpoint_names,
    list_deployment_names,
    CustomConnectionsContainer,
    get_model_type,
    ModelFamily
)
from promptflow.tools.open_source_llm import (
    OpenSourceLLM,
    API,
    ContentFormatterBase,
    LlamaContentFormatter,
    list_endpoint_names,
    list_deployment_names,
    CustomConnectionsContainer,
    get_model_type,
    ModelFamily
)


@pytest.fixture
def endpoints_provider(open_source_llm_ws_service_connection) -> Dict[str, List[str]]:
    if not open_source_llm_ws_service_connection:
        pytest.skip("Service Credential not available")

    from azure.ai.ml import MLClient
    from azure.identity import DefaultAzureCredential
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


@pytest.mark.usefixtures("use_secrets_config_file")
class TestOpenSourceLLM:
    stateless_os_llm = OpenSourceLLM()
    gpt2_connection = "connection/gpt2_connection"
    llama_connection = "connection/llama_chat_connection"
    llama_serverless_connection = "connection/llama_serverless_connection"
    completion_prompt = "In the context of Azure ML, what does the ML stand for?"
    chat_prompt = """system:
You are a AI which helps Customers answer questions.

user:
""" + completion_prompt

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_completion(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(
    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_completion(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(
            self.completion_prompt,
            API.COMPLETION,
            endpoint=self.gpt2_connection)
            API.COMPLETION,
            endpoint=self.gpt2_connection)
        assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_completion_with_deploy(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(
    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_completion_with_deploy(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(
            self.completion_prompt,
            API.COMPLETION,
            endpoint=self.gpt2_connection,
            endpoint=self.gpt2_connection,
            deployment_name="gpt2-9")
        assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_chat(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(
    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_chat(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(
            self.chat_prompt,
            API.CHAT,
            endpoint=self.gpt2_connection)
            API.CHAT,
            endpoint=self.gpt2_connection)
        assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_chat_with_deploy(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(
    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_chat_with_deploy(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(
            self.chat_prompt,
            API.CHAT,
            endpoint=self.gpt2_connection,
            endpoint=self.gpt2_connection,
            deployment_name="gpt2-9")
        assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_chat_with_max_length(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(
    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_chat_with_max_length(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(
            self.chat_prompt,
            API.CHAT,
            endpoint=self.gpt2_connection,
            endpoint=self.gpt2_connection,
            max_new_tokens=2)
        # GPT-2 doesn't take this parameter
        assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("gpt2_custom_connection")
    def test_open_source_llm_con_url_chat(self, gpt2_custom_connection):
        tmp = copy.deepcopy(gpt2_custom_connection)
        del tmp.configs['endpoint_url']
        with pytest.raises(OpenSourceLLMKeyValidationError) as exc_info:
            customConnectionsContainer = CustomConnectionsContainer()
            customConnectionsContainer.get_endpoint_from_custom_connection(connection=tmp)
            customConnectionsContainer = CustomConnectionsContainer()
            customConnectionsContainer.get_endpoint_from_custom_connection(connection=tmp)
        assert exc_info.value.message == """Required key `endpoint_url` not found in given custom connection.
Required keys are: endpoint_url,model_family."""
        assert exc_info.value.error_codes == "UserError/ToolValidationError/OpenSourceLLMKeyValidationError".split("/")

    @pytest.mark.skip_if_no_api_key("gpt2_custom_connection")
    def test_open_source_llm_con_key_chat(self, gpt2_custom_connection):
        tmp = copy.deepcopy(gpt2_custom_connection)
        del tmp.secrets['endpoint_api_key']
        with pytest.raises(OpenSourceLLMKeyValidationError) as exc_info:
            customConnectionsContainer = CustomConnectionsContainer()
            customConnectionsContainer.get_endpoint_from_custom_connection(connection=tmp)
            customConnectionsContainer = CustomConnectionsContainer()
            customConnectionsContainer.get_endpoint_from_custom_connection(connection=tmp)
        assert exc_info.value.message == (
            "Required secret key `endpoint_api_key` "
            + """not found in given custom connection.
Required keys are: endpoint_api_key.""")
        assert exc_info.value.error_codes == "UserError/ToolValidationError/OpenSourceLLMKeyValidationError".split("/")

    @pytest.mark.skip_if_no_api_key("gpt2_custom_connection")
    def test_open_source_llm_con_model_chat(self, gpt2_custom_connection):
        tmp = copy.deepcopy(gpt2_custom_connection)
        del tmp.configs['model_family']
        with pytest.raises(OpenSourceLLMKeyValidationError) as exc_info:
            customConnectionsContainer = CustomConnectionsContainer()
            customConnectionsContainer.get_endpoint_from_custom_connection(connection=tmp)
            customConnectionsContainer = CustomConnectionsContainer()
            customConnectionsContainer.get_endpoint_from_custom_connection(connection=tmp)
        assert exc_info.value.message == """Required key `model_family` not found in given custom connection.
Required keys are: endpoint_url,model_family."""
        assert exc_info.value.error_codes == "UserError/ToolValidationError/OpenSourceLLMKeyValidationError".split("/")

    def test_open_source_llm_escape_chat(self):
        danger = r"The quick \brown fox\tjumped\\over \the \\boy\r\n"
        out_of_danger = ContentFormatterBase.escape_special_characters(danger)
        assert out_of_danger == "The quick \\brown fox\\tjumped\\\\over \\the \\\\boy\\r\\n"

    def test_open_source_llm_llama_parse_chat_with_chat(self):
        LlamaContentFormatter.parse_chat(self.chat_prompt)

    def test_open_source_llm_llama_parse_multi_turn(self):
        multi_turn_chat = """user:
You are a AI which helps Customers answer questions.

What is the best movie of all time?

assistant:
Mobius, which starred Jared Leto

user:
Why was that the greatest movie of all time?
"""
        LlamaContentFormatter.parse_chat(multi_turn_chat)

    def test_open_source_llm_llama_parse_ignore_whitespace(self):
        bad_chat_prompt = f"""system:
You are a AI which helps Customers answer questions.

user:

user:
{self.completion_prompt}"""
        with pytest.raises(OpenSourceLLMUserError) as exc_info:
            LlamaContentFormatter.parse_chat(bad_chat_prompt)
        assert exc_info.value.message == (
            "The Chat API requires a specific format for prompt definition, and the prompt should include separate "
            + "lines as role delimiters: 'assistant:\\n','system:\\n','user:\\n'. Current parsed role 'in the context "
            + "of azure ml, what does the ml stand for?' does not meet the requirement. If you intend to use the "
            + "Completion API, please select the appropriate API type and deployment name. If you do intend to use "
            + "the Chat API, please refer to the guideline at https://aka.ms/pfdoc/chat-prompt or view the samples in "
            + "our gallery that contain 'Chat' in the name.")
        assert exc_info.value.error_codes == "UserError/OpenSourceLLMUserError".split("/")

    def test_open_source_llm_llama_parse_chat_with_comp(self):
        with pytest.raises(OpenSourceLLMUserError) as exc_info:
            LlamaContentFormatter.parse_chat(self.completion_prompt)
        assert exc_info.value.message == (
            "The Chat API requires a specific format for prompt definition, and the prompt should include separate "
            + "lines as role delimiters: 'assistant:\\n','system:\\n','user:\\n'. Current parsed role 'in the context "
            + "of azure ml, what does the ml stand for?' does not meet the requirement. If you intend to use the "
            + "Completion API, please select the appropriate API type and deployment name. If you do intend to use the "
            + "Chat API, please refer to the guideline at https://aka.ms/pfdoc/chat-prompt or view the samples in our "
            + "gallery that contain 'Chat' in the name.")
        assert exc_info.value.error_codes == "UserError/OpenSourceLLMUserError".split("/")

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_chat_endpoint_name(self, chat_endpoints_provider):
        for endpoint_name in chat_endpoints_provider:
            response = self.stateless_os_llm.call(
                self.chat_prompt,
                API.CHAT,
                endpoint=f"onlineEndpoint/{endpoint_name}")
            response = self.stateless_os_llm.call(
                self.chat_prompt,
                API.CHAT,
                endpoint=f"onlineEndpoint/{endpoint_name}")
            assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_chat_endpoint_name_with_deployment(self, chat_endpoints_provider):
        for endpoint_name in chat_endpoints_provider:
            for deployment_name in chat_endpoints_provider[endpoint_name]:
                response = self.stateless_os_llm.call(
                    self.chat_prompt,
                    API.CHAT,
                    endpoint=f"onlineEndpoint/{endpoint_name}",
                    deployment_name=deployment_name)
                response = self.stateless_os_llm.call(
                    self.chat_prompt,
                    API.CHAT,
                    endpoint=f"onlineEndpoint/{endpoint_name}",
                    deployment_name=deployment_name)
                assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_completion_endpoint_name(self, completion_endpoints_provider):
        for endpoint_name in completion_endpoints_provider:
            response = self.stateless_os_llm.call(
                self.completion_prompt,
                API.COMPLETION,
                endpoint=f"onlineEndpoint/{endpoint_name}")
            response = self.stateless_os_llm.call(
                self.completion_prompt,
                API.COMPLETION,
                endpoint=f"onlineEndpoint/{endpoint_name}")
            assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_completion_endpoint_name_with_deployment(self, completion_endpoints_provider):
        for endpoint_name in completion_endpoints_provider:
            for deployment_name in completion_endpoints_provider[endpoint_name]:
                response = self.stateless_os_llm.call(
                    self.completion_prompt,
                    API.COMPLETION,
                    endpoint=f"onlineEndpoint/{endpoint_name}",
                    deployment_name=deployment_name)
                response = self.stateless_os_llm.call(
                    self.completion_prompt,
                    API.COMPLETION,
                    endpoint=f"onlineEndpoint/{endpoint_name}",
                    deployment_name=deployment_name)
                assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_llama_chat(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(self.chat_prompt, API.CHAT, endpoint=self.llama_connection)
        assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_llama_serverless(self, chat_endpoints_provider):
        response = self.stateless_os_llm.call(
            self.completion_prompt,
            API.COMPLETION,
            endpoint=self.llama_serverless_connection)
        assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_llama_chat_history(self, chat_endpoints_provider):
    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_llama_chat_history(self, chat_endpoints_provider):
        chat_history_prompt = """user:
* Given the following conversation history and the users next question, answer the next question.
If the conversation is irrelevant or empty, just restate the original question.
Do not add more details than necessary to the question.

assistant:
skip

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
        response = self.stateless_os_llm.call(
            chat_history_prompt,
            API.CHAT,
            endpoint=self.llama_connection,
            endpoint=self.llama_connection,
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
        assert len(response) > 25

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_dynamic_list_ignore_deployment(self):
        deployments = list_deployment_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            endpoint=None)
        assert len(deployments) == 0

        deployments = list_deployment_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            endpoint='')
        assert len(deployments) == 0

        deployments = list_deployment_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            endpoint='fake_endpoint name')
        assert len(deployments) == 0

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_dynamic_list_happy_path(self, chat_endpoints_provider):
        # workaround to set env variables from service credential
        print(chat_endpoints_provider)

        endpoints = list_endpoint_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"))
        # we might want to remove this or skip if there are zero endpoints in the long term.
        # currently we have low cost compute for a GPT2 endpoint, so if nothing else this should be available.
        assert len(endpoints) > 0

        for endpoint in endpoints:
            prompt = self.chat_prompt if "chat" in endpoint['value'] else self.completion_prompt
            api_type = API.CHAT if "chat" in endpoint['value'] else API.COMPLETION

            # test with default endpoint
            response = self.stateless_os_llm.call(
                prompt,
                api_type,
                endpoint=endpoint['value'])
            assert len(response) > 25

            deployments = list_deployment_names(
                subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
                resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
                workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
                endpoint=endpoint['value'])
            if "onlineEndpoint" in endpoint['value']:
                assert len(deployments) > 0
            else:
                assert len(deployments) == 0

            for deployment in deployments:
                response = self.stateless_os_llm.call(
                    prompt,
                    api_type,
                    endpoint=endpoint['value'],
                    deployment_name=deployment['value'])
                assert len(response) > 25

    def test_open_source_llm_get_model_llama(self):
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

    def test_open_source_llm_get_model_gpt2(self):
        model_assets = [
            "azureml://registries/azureml-staging/models/gpt2/versions/9",
            "azureml://registries/azureml/models/gpt2/versions/9",
            "azureml://registries/azureml/models/gpt2-medium/versions/11",
            "azureml://registries/azureml/models/gpt2-large/versions/11"
        ]

        for asset_name in model_assets:
            assert ModelFamily.GPT2 == get_model_type(asset_name)

    def test_open_source_llm_get_model_dolly(self):
        model_assets = [
            "azureml://registries/azureml/models/databricks-dolly-v2-12b/versions/11"
        ]

        for asset_name in model_assets:
            assert ModelFamily.DOLLY == get_model_type(asset_name)

    def test_open_source_llm_get_model_falcon(self):
        model_assets = [
            "azureml://registries/azureml/models/tiiuae-falcon-40b/versions/2",
            "azureml://registries/azureml/models/tiiuae-falcon-40b/versions/2"
        ]

        for asset_name in model_assets:
            assert ModelFamily.FALCON == get_model_type(asset_name)

    def test_open_source_llm_get_model_failure_cases(self):
        bad_model_assets = [
            "azureml://registries/azureml-meta/models/CodeLlama-7b-Instruct-hf/versions/3",
            "azureml://registries/azureml-staging/models/gpt-2/versions/9",
            "azureml://registries/azureml/models/falcon-40b/versions/2",
            "azureml://registries/azureml-meta/models/Llama-70b/versions/13",
            "azureml://registries/azureml/models/openai-whisper-large/versions/14",
            "azureml://registries/azureml/models/ask-wikipedia/versions/2"
        ]

        for asset_name in bad_model_assets:
            val = get_model_type(asset_name)
            assert val is None

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_dynamic_list_ignore_deployment(self):
        deployments = list_deployment_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            endpoint=None)
        assert len(deployments) == 0

        deployments = list_deployment_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            endpoint='')
        assert len(deployments) == 0

        deployments = list_deployment_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
            endpoint='fake_endpoint name')
        assert len(deployments) == 0

    @pytest.mark.skip_if_no_api_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_dynamic_list_happy_path(self, chat_endpoints_provider):
        # workaround to set env variables from service credential
        print(chat_endpoints_provider)

        endpoints = list_endpoint_names(
            subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
            resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
            workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"))
        # we might want to remove this or skip if there are zero endpoints in the long term.
        # currently we have low cost compute for a GPT2 endpoint, so if nothing else this should be available.
        assert len(endpoints) > 0

        for endpoint in endpoints:
            prompt = self.chat_prompt if "chat" in endpoint['value'] else self.completion_prompt
            api_type = API.CHAT if "chat" in endpoint['value'] else API.COMPLETION

            # test with default endpoint
            response = self.stateless_os_llm.call(
                prompt,
                api_type,
                endpoint=endpoint['value'])
            assert len(response) > 25

            deployments = list_deployment_names(
                subscription_id=os.getenv("AZUREML_ARM_SUBSCRIPTION"),
                resource_group_name=os.getenv("AZUREML_ARM_RESOURCEGROUP"),
                workspace_name=os.getenv("AZUREML_ARM_WORKSPACE_NAME"),
                endpoint=endpoint['value'])
            if "onlineEndpoint" in endpoint['value']:
                assert len(deployments) > 0
            else:
                assert len(deployments) == 0

            for deployment in deployments:
                response = self.stateless_os_llm.call(
                    prompt,
                    api_type,
                    endpoint=endpoint['value'],
                    deployment_name=deployment['value'])
                assert len(response) > 25

    def test_open_source_llm_get_model_llama(self):
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

    def test_open_source_llm_get_model_gpt2(self):
        model_assets = [
            "azureml://registries/azureml-staging/models/gpt2/versions/9",
            "azureml://registries/azureml/models/gpt2/versions/9",
            "azureml://registries/azureml/models/gpt2-medium/versions/11",
            "azureml://registries/azureml/models/gpt2-large/versions/11"
        ]

        for asset_name in model_assets:
            assert ModelFamily.GPT2 == get_model_type(asset_name)

    def test_open_source_llm_get_model_dolly(self):
        model_assets = [
            "azureml://registries/azureml/models/databricks-dolly-v2-12b/versions/11"
        ]

        for asset_name in model_assets:
            assert ModelFamily.DOLLY == get_model_type(asset_name)

    def test_open_source_llm_get_model_falcon(self):
        model_assets = [
            "azureml://registries/azureml/models/tiiuae-falcon-40b/versions/2",
            "azureml://registries/azureml/models/tiiuae-falcon-40b/versions/2"
        ]

        for asset_name in model_assets:
            assert ModelFamily.FALCON == get_model_type(asset_name)

    def test_open_source_llm_get_model_failure_cases(self):
        bad_model_assets = [
            "azureml://registries/azureml-meta/models/CodeLlama-7b-Instruct-hf/versions/3",
            "azureml://registries/azureml-staging/models/gpt-2/versions/9",
            "azureml://registries/azureml/models/falcon-40b/versions/2",
            "azureml://registries/azureml-meta/models/Llama-70b/versions/13",
            "azureml://registries/azureml/models/openai-whisper-large/versions/14",
            "azureml://registries/azureml/models/ask-wikipedia/versions/2"
        ]

        for asset_name in bad_model_assets:
            val = get_model_type(asset_name)
            assert val is None

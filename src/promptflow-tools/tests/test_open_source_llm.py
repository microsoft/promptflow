import copy
import os
import pytest
from promptflow.tools.exception import (
    OpenSourceLLMOnlineEndpointError,
    OpenSourceLLMUserError,
    OpenSourceLLMKeyValidationError
)
from promptflow.tools.open_source_llm import OpenSourceLLM, API, ContentFormatterBase, LlamaContentFormatter
from typing import List, Dict


@pytest.fixture
def gpt2_provider(gpt2_custom_connection) -> OpenSourceLLM:
    return OpenSourceLLM(gpt2_custom_connection)


@pytest.fixture
def llama_chat_provider(llama_chat_custom_connection) -> OpenSourceLLM:
    return OpenSourceLLM(llama_chat_custom_connection)


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
    completion_prompt = "In the context of Azure ML, what does the ML stand for?"

    chat_prompt = """system:
You are a AI which helps Customers answer questions.

user:
""" + completion_prompt

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_completion(self, gpt2_provider):
        response = gpt2_provider.call(
            self.completion_prompt,
            API.COMPLETION)
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_completion_with_deploy(self, gpt2_provider):
        response = gpt2_provider.call(
            self.completion_prompt,
            API.COMPLETION,
            deployment_name="gpt2-9")
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_chat(self, gpt2_provider):
        response = gpt2_provider.call(
            self.chat_prompt,
            API.CHAT)
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_chat_with_deploy(self, gpt2_provider):
        response = gpt2_provider.call(
            self.chat_prompt,
            API.CHAT,
            deployment_name="gpt2-9")
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_chat_with_max_length(self, gpt2_provider):
        response = gpt2_provider.call(
            self.chat_prompt,
            API.CHAT,
            max_new_tokens=2)
        # GPT-2 doesn't take this parameter
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_con_url_chat(self, gpt2_custom_connection):
        tmp = copy.deepcopy(gpt2_custom_connection)
        del tmp.configs['endpoint_url']
        with pytest.raises(OpenSourceLLMKeyValidationError) as exc_info:
            os = OpenSourceLLM(tmp)
            os.call(self.chat_prompt, API.CHAT)
        assert exc_info.value.message == """Required key `endpoint_url` not found in given custom connection.
Required keys are: endpoint_url,model_family."""
        assert exc_info.value.error_codes == "UserError/ToolValidationError/OpenSourceLLMKeyValidationError".split("/")

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_con_key_chat(self, gpt2_custom_connection):
        tmp = copy.deepcopy(gpt2_custom_connection)
        del tmp.secrets['endpoint_api_key']
        with pytest.raises(OpenSourceLLMKeyValidationError) as exc_info:
            os = OpenSourceLLM(tmp)
            os.call(self.chat_prompt, API.CHAT)
        assert exc_info.value.message == (
            "Required secret key `endpoint_api_key` "
            + """not found in given custom connection.
Required keys are: endpoint_api_key.""")
        assert exc_info.value.error_codes == "UserError/ToolValidationError/OpenSourceLLMKeyValidationError".split("/")

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_con_model_chat(self, gpt2_custom_connection):
        tmp = copy.deepcopy(gpt2_custom_connection)
        del tmp.configs['model_family']
        with pytest.raises(OpenSourceLLMKeyValidationError) as exc_info:
            os = OpenSourceLLM(tmp)
            os.call(self.completion_prompt, API.COMPLETION)
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

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_llama_endpoint_miss(self, gpt2_custom_connection):
        tmp = copy.deepcopy(gpt2_custom_connection)
        tmp.configs['endpoint_url'] += 'completely/real/endpoint'
        os = OpenSourceLLM(tmp)
        with pytest.raises(OpenSourceLLMOnlineEndpointError) as exc_info:
            os.call(
                self.completion_prompt,
                API.COMPLETION)
        assert exc_info.value.message == (
            "Exception hit calling Oneline Endpoint: "
            + "HTTPError: HTTP Error 424: Failed Dependency")
        assert exc_info.value.error_codes == "UserError/OpenSourceLLMOnlineEndpointError".split("/")

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_llama_deployment_miss(self, gpt2_provider):
        with pytest.raises(OpenSourceLLMOnlineEndpointError) as exc_info:
            gpt2_provider.call(self.completion_prompt,
                               API.COMPLETION,
                               deployment_name="completely/real/deployment-007")
        assert exc_info.value.message == (
            "Exception hit calling Oneline Endpoint: "
            + "HTTPError: HTTP Error 404: Not Found")
        assert exc_info.value.error_codes == "UserError/OpenSourceLLMOnlineEndpointError".split("/")

    @pytest.mark.skip_if_no_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_chat_endpoint_name(self, chat_endpoints_provider):
        for endpoint_name in chat_endpoints_provider:
            os_llm = OpenSourceLLM(endpoint_name=endpoint_name)
            response = os_llm.call(self.chat_prompt, API.CHAT)
            assert len(response) > 25

    @pytest.mark.skip_if_no_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_chat_endpoint_name_with_deployment(self, chat_endpoints_provider):
        for endpoint_name in chat_endpoints_provider:
            os_llm = OpenSourceLLM(endpoint_name=endpoint_name)
            for deployment_name in chat_endpoints_provider[endpoint_name]:
                response = os_llm.call(self.chat_prompt, API.CHAT, deployment_name=deployment_name)
                assert len(response) > 25

    @pytest.mark.skip_if_no_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_completion_endpoint_name(self, completion_endpoints_provider):
        for endpoint_name in completion_endpoints_provider:
            os_llm = OpenSourceLLM(endpoint_name=endpoint_name)
            response = os_llm.call(self.completion_prompt, API.COMPLETION)
            assert len(response) > 25

    @pytest.mark.skip_if_no_key("open_source_llm_ws_service_connection")
    def test_open_source_llm_completion_endpoint_name_with_deployment(self, completion_endpoints_provider):
        for endpoint_name in completion_endpoints_provider:
            os_llm = OpenSourceLLM(endpoint_name=endpoint_name)
            for deployment_name in completion_endpoints_provider[endpoint_name]:
                response = os_llm.call(self.completion_prompt, API.COMPLETION, deployment_name=deployment_name)
                assert len(response) > 25

    @pytest.mark.skip_if_no_key("llama_chat_custom_connection")
    def test_open_source_llm_llama_chat(self, llama_chat_provider):
        response = llama_chat_provider.call(self.chat_prompt, API.CHAT)
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("llama_chat_custom_connection")
    def test_open_source_llm_llama_chat_history(self, llama_chat_provider):
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
        response = llama_chat_provider.call(
            chat_history_prompt,
            API.CHAT,
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

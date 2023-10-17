import os
import pytest
from promptflow.tools.exception import (
    OpenSourceLLMOnlineEndpointError,
    OpenSourceLLMUserError,
    OpenSourceLLMKeyValidationError
)
from promptflow.tools.open_source_llm import OpenSourceLLM, API, ContentFormatterBase, LlamaContentFormatter


@pytest.fixture
def gpt2_provider(gpt2_custom_connection) -> OpenSourceLLM:
    return OpenSourceLLM(gpt2_custom_connection)


@pytest.fixture
def llama_chat_provider(llama_chat_custom_connection) -> OpenSourceLLM:
    return OpenSourceLLM(llama_chat_custom_connection)


@pytest.mark.usefixtures("use_secrets_config_file")
class TestOpenSourceLLM:
    completion_prompt = "In the context of Azure ML, what does the ML stand for?"

    gpt2_chat_prompt = """user:
You are a AI which helps Customers answer questions.

user:
""" + completion_prompt

    llama_chat_prompt = """user:
You are a AI which helps Customers answer questions.

""" + completion_prompt

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_completion(self, gpt2_provider):
        response = gpt2_provider.call(
            self.completion_prompt,
            API.COMPLETION)
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_completion_with_deploy(self, gpt2_custom_connection):
        os_tool = OpenSourceLLM(
            gpt2_custom_connection,
            deployment_name="gpt2-8")
        response = os_tool.call(
            self.completion_prompt,
            API.COMPLETION)
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_chat(self, gpt2_provider):
        response = gpt2_provider.call(
            self.gpt2_chat_prompt,
            API.CHAT)
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_chat_with_deploy(self, gpt2_custom_connection):
        os_tool = OpenSourceLLM(
            gpt2_custom_connection,
            deployment_name="gpt2-8")
        response = os_tool.call(
            self.gpt2_chat_prompt,
            API.CHAT)
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_chat_with_max_length(self, gpt2_provider):
        response = gpt2_provider.call(
            self.gpt2_chat_prompt,
            API.CHAT,
            max_new_tokens=2)
        # GPT-2 doesn't take this parameter
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_con_url_chat(self, gpt2_custom_connection):
        del gpt2_custom_connection.configs['endpoint_url']
        with pytest.raises(OpenSourceLLMKeyValidationError) as exc_info:
            os = OpenSourceLLM(gpt2_custom_connection)
            os.call(self.chat_prompt, API.CHAT)
        assert exc_info.value.message == """Required key `endpoint_url` not found in given custom connection.
Required keys are: endpoint_url,model_family."""
        assert exc_info.value.error_codes == "UserError/ToolValidationError/OpenSourceLLMKeyValidationError".split("/")

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_con_key_chat(self, gpt2_custom_connection):
        del gpt2_custom_connection.secrets['endpoint_api_key']
        with pytest.raises(OpenSourceLLMKeyValidationError) as exc_info:
            os = OpenSourceLLM(gpt2_custom_connection)
            os.call(self.chat_prompt, API.CHAT)
        assert exc_info.value.message == (
            "Required secret key `endpoint_api_key` "
            + """not found in given custom connection.
Required keys are: endpoint_api_key.""")
        assert exc_info.value.error_codes == "UserError/ToolValidationError/OpenSourceLLMKeyValidationError".split("/")

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_con_model_chat(self, gpt2_custom_connection):
        del gpt2_custom_connection.configs['model_family']
        with pytest.raises(OpenSourceLLMKeyValidationError) as exc_info:
            os = OpenSourceLLM(gpt2_custom_connection)
            os.call(self.completion_prompt, API.COMPLETION)
        assert exc_info.value.message == """Required key `model_family` not found in given custom connection.
Required keys are: endpoint_url,model_family."""
        assert exc_info.value.error_codes == "UserError/ToolValidationError/OpenSourceLLMKeyValidationError".split("/")

    def test_open_source_llm_escape_chat(self):
        danger = r"The quick \brown fox\tjumped\\over \the \\boy\r\n"
        out_of_danger = ContentFormatterBase.escape_special_characters(danger)
        assert out_of_danger == "The quick \\brown fox\\tjumped\\\\over \\the \\\\boy\\r\\n"

    def test_open_source_llm_llama_parse_chat_with_chat(self):
        LlamaContentFormatter.parse_chat(self.llama_chat_prompt)

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

    def test_open_source_llm_llama_parse_system_not_accepted(self):
        bad_chat_prompt = """system:
You are a AI which helps Customers answer questions.

user:
""" + self.completion_prompt
        with pytest.raises(OpenSourceLLMUserError) as exc_info:
            LlamaContentFormatter.parse_chat(bad_chat_prompt)
        assert exc_info.value.message == (
            "The Chat API requires a specific format for prompt definition,"
            + " and the prompt should include separate lines as role delimiters: 'assistant:\\n','user:\\n'."
            + " Current parsed role 'system' does not meet the requirement. If you intend to use the Completion "
            + "API, please select the appropriate API type and deployment name. If you do intend to use the Chat "
            + "API, please refer to the guideline at https://aka.ms/pfdoc/chat-prompt or view the samples in our "
            + "gallery that contain 'Chat' in the name.")
        assert exc_info.value.error_codes == "UserError/OpenSourceLLMUserError".split("/")

    def test_open_source_llm_llama_parse_ignore_whitespace(self):
        bad_chat_prompt = f"""system:
You are a AI which helps Customers answer questions.

user:

user:
{self.completion_prompt}"""
        with pytest.raises(OpenSourceLLMUserError) as exc_info:
            LlamaContentFormatter.parse_chat(bad_chat_prompt)
        assert exc_info.value.message == (
            "The Chat API requires a specific format for prompt definition, and "
            + "the prompt should include separate lines as role delimiters: 'assistant:\\n','user:\\n'. Current parsed "
            + "role 'system' does not meet the requirement. If you intend to use the Completion API, please select the "
            + "appropriate API type and deployment name. If you do intend to use the Chat API, please refer to the "
            + "guideline at https://aka.ms/pfdoc/chat-prompt or view the samples in our gallery that contain 'Chat' "
            + "in the name.")
        assert exc_info.value.error_codes == "UserError/OpenSourceLLMUserError".split("/")

    def test_open_source_llm_llama_parse_chat_with_comp(self):
        with pytest.raises(OpenSourceLLMUserError) as exc_info:
            LlamaContentFormatter.parse_chat(self.completion_prompt)
        assert exc_info.value.message == (
            "The Chat API requires a specific format for prompt definition, and "
            + "the prompt should include separate lines as role delimiters: 'assistant:\\n','user:\\n'. Current parsed "
            + "role 'in the context of azure ml, what does the ml stand for?' does not meet the requirement. If you "
            + "intend to use the Completion API, please select the appropriate API type and deployment name. If you do "
            + "intend to use the Chat API, please refer to the guideline at https://aka.ms/pfdoc/chat-prompt or view "
            + "the samples in our gallery that contain 'Chat' in the name.")
        assert exc_info.value.error_codes == "UserError/OpenSourceLLMUserError".split("/")

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_llama_endpoint_miss(self, gpt2_custom_connection):
        gpt2_custom_connection.configs['endpoint_url'] += 'completely/real/endpoint'
        os = OpenSourceLLM(gpt2_custom_connection)
        with pytest.raises(OpenSourceLLMOnlineEndpointError) as exc_info:
            os.call(
                self.completion_prompt,
                API.COMPLETION)
        assert exc_info.value.message == (
            "Exception hit calling Oneline Endpoint: "
            + "HTTPError: HTTP Error 424: Failed Dependency")
        assert exc_info.value.error_codes == "UserError/OpenSourceLLMOnlineEndpointError".split("/")

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_llama_deployment_miss(self, gpt2_custom_connection):
        os = OpenSourceLLM(
            gpt2_custom_connection,
            deployment_name="completely/real/deployment-007")
        with pytest.raises(OpenSourceLLMOnlineEndpointError) as exc_info:
            os.call(self.completion_prompt, API.COMPLETION)
        assert exc_info.value.message == (
            "Exception hit calling Oneline Endpoint: "
            + "HTTPError: HTTP Error 404: Not Found")
        assert exc_info.value.error_codes == "UserError/OpenSourceLLMOnlineEndpointError".split("/")

    @pytest.mark.skip
    def test_open_source_llm_endpoint_name(self):
        os.environ["AZUREML_ARM_SUBSCRIPTION"] = "<needs_value>"
        os.environ["AZUREML_ARM_RESOURCEGROUP"] = "<needs_value>"
        os.environ["AZUREML_ARM_WORKSPACE_NAME"] = "<needs_value>"

        os_llm = OpenSourceLLM(endpoint_name="llama-temp-chat")
        response = os_llm.call(self.llama_chat_prompt, API.CHAT)
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("llama_chat_custom_connection")
    def test_open_source_llm_llama_chat(self, llama_chat_provider):
        response = llama_chat_provider.call(self.llama_chat_prompt, API.CHAT)
        assert len(response) > 25

    @pytest.mark.skip_if_no_key("llama_chat_custom_connection")
    def test_open_source_llm_llama_chat_history(self, llama_chat_provider):
        chat_history_prompt = """user: 
* Given the following conversation history and the users next question,rephrase the question to be a stand alone question.
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
Follow up Input: {{ chat_input }}"""
        response = llama_chat_provider.call(
            chat_history_prompt,
            API.CHAT,
            chat_history = [
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
                        "chat_output": "An Azure Machine Learning compute instance is a fully managed cloud-based workstation for data scientists. It provides a pre-configured and managed development environment in the cloud for machine learning. Compute instances can also be used as a compute target for training and inferencing for development and testing purposes. They have a job queue, run jobs securely in a virtual network environment, and can run multiple small jobs in parallel. Additionally, compute instances support single-node multi-GPU distributed training jobs."
                    }
                }
            ],
            chat_input = "Sorry I didn't follow, could you say that again?")
        assert len(response) > 25

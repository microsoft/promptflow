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


@pytest.mark.usefixtures("use_secrets_config_file")
class TestOpenSourceLLM:
    completion_prompt = "In the context of Azure ML, what does the ML stand for?"
    chat_prompt = """user:
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
            deployment_name="gpt2-8")
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
            deployment_name="gpt2-8")
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
        os = OpenSourceLLM(gpt2_custom_connection)
        with pytest.raises(OpenSourceLLMOnlineEndpointError) as exc_info:
            os.call(
                self.completion_prompt,
                API.COMPLETION,
                deployment_name="completely/real/deployment-007")
        assert exc_info.value.message == (
            "Exception hit calling Oneline Endpoint: "
            + "HTTPError: HTTP Error 404: Not Found")
        assert exc_info.value.error_codes == "UserError/OpenSourceLLMOnlineEndpointError".split("/")

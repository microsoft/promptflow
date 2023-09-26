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
        try:
            os = OpenSourceLLM(gpt2_custom_connection)
            os.call(self.chat_prompt, API.CHAT)
            assert False
        except OpenSourceLLMKeyValidationError:
            pass

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_con_key_chat(self, gpt2_custom_connection):
        del gpt2_custom_connection.secrets['endpoint_api_key']
        try:
            os = OpenSourceLLM(gpt2_custom_connection)
            os.call(self.chat_prompt, API.CHAT)
            assert False
        except OpenSourceLLMKeyValidationError:
            pass

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_con_model_chat(self, gpt2_custom_connection):
        del gpt2_custom_connection.configs['model_family']
        try:
            os = OpenSourceLLM(gpt2_custom_connection)
            os.call(self.completion_prompt, API.COMPLETION)
            assert False
        except OpenSourceLLMKeyValidationError:
            pass

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
        try:
            LlamaContentFormatter.parse_chat(bad_chat_prompt)
            assert False
        except OpenSourceLLMUserError:
            pass

    def test_open_source_llm_llama_parse_ignore_whitespace(self):
        bad_chat_prompt = f"""system:
You are a AI which helps Customers answer questions.

user:

user:
{self.completion_prompt}"""
        try:
            LlamaContentFormatter.parse_chat(bad_chat_prompt)
            assert False
        except OpenSourceLLMUserError:
            pass

    def test_open_source_llm_llama_parse_chat_with_comp(self):
        try:
            LlamaContentFormatter.parse_chat(self.completion_prompt)
            assert False
        except OpenSourceLLMUserError:
            pass

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_llama_req_chat(self, gpt2_custom_connection):
        gpt2_custom_connection.configs['endpoint_url'] += 'completely/real/endpoint'
        os = OpenSourceLLM(gpt2_custom_connection)
        try:
            os.call(
                self.completion_prompt,
                API.COMPLETION)
        except OpenSourceLLMOnlineEndpointError:
            pass

    @pytest.mark.skip_if_no_key("gpt2_custom_connection")
    def test_open_source_llm_llama_req_chat(self, gpt2_custom_connection):
        os = OpenSourceLLM(gpt2_custom_connection)
        try:
            os.call(
                self.completion_prompt,
                API.COMPLETION,
                deployment_name="completely/real/deployment-007")
        except OpenSourceLLMOnlineEndpointError:
            pass

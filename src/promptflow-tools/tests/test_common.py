import pytest

from promptflow.tools.common import try_parse_name_and_content, ChatAPIInvalidFunctions, validate_functions, \
    process_function_call, parse_chat


class TestCommon:
    @pytest.mark.parametrize(
        "functions, error_message",
        [
            ([], "functions cannot be an empty list"),
            (["str"],
             "is not a dict. Here is a valid function example"),
            ([{"name": "func1"}], "does not have 'parameters' property"),
            ([{"name": "func1", "parameters": "param1"}],
             "should be described as a JSON Schema object"),
            ([{"name": "func1", "parameters": {"type": "int", "properties": {}}}],
             "parameters 'type' should be 'object'"),
            ([{"name": "func1", "parameters": {"type": "object", "properties": []}}],
             "should be described as a JSON Schema object"),
        ],
    )
    def test_chat_api_invalid_functions(self, functions, error_message):
        error_codes = "UserError/ToolValidationError/ChatAPIInvalidFunctions"
        with pytest.raises(ChatAPIInvalidFunctions) as exc_info:
            validate_functions(functions)
        assert error_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    @pytest.mark.parametrize(
        "function_call, error_message",
        [
            ("123", "function_call parameter '123' must be a dict"),
            ({"name1": "get_current_weather"},
             'function_call parameter {"name1": "get_current_weather"} must '
             'contain "name" field'),
        ],
    )
    def test_chat_api_invalid_function_call(self, function_call, error_message):
        error_codes = "UserError/ToolValidationError/ChatAPIInvalidFunctions"
        with pytest.raises(ChatAPIInvalidFunctions) as exc_info:
            process_function_call(function_call)
        assert error_message in exc_info.value.message
        assert exc_info.value.error_codes == error_codes.split("/")

    @pytest.mark.parametrize(
        "chat_str, expected_result",
        [
            ("system:\nthis is my function:\ndef hello", [
                {'role': 'system', 'content': 'this is my function:\ndef hello'}]),
            ("#system:\nthis is my ##function:\ndef hello", [
                {'role': 'system', 'content': 'this is my ##function:\ndef hello'}]),
            (" \n system:\nthis is my function:\ndef hello", [
                {'role': 'system', 'content': 'this is my function:\ndef hello'}]),
            (" \n # system:\nthis is my function:\ndef hello", [
                {'role': 'system', 'content': 'this is my function:\ndef hello'}]),
            ("user:\nhi\nassistant:\nanswer\nfunction:\nname:\nn\ncontent:\nc", [
                {'role': 'user', 'content': 'hi'},
                {'role': 'assistant', 'content': 'answer'},
                {'role': 'function', 'name': 'n', 'content': 'c'}]),
            ("#user :\nhi\n #assistant:\nanswer\n# function:\n##name:\nn\n##content:\nc", [
                {'role': 'user', 'content': 'hi'},
                {'role': 'assistant', 'content': 'answer'},
                {'role': 'function', 'name': 'n', 'content': 'c'}]),
            ("\nsystem:\nfirst\n\nsystem:\nsecond", [
                {'role': 'system', 'content': 'first'}, {'role': 'system', 'content': 'second'}]),
            ("\n#system:\nfirst\n\n#system:\nsecond", [
                {'role': 'system', 'content': 'first'}, {'role': 'system', 'content': 'second'}])
        ]
    )
    def test_success_parse_role_prompt(self, chat_str, expected_result):
        actual_result = parse_chat(chat_str)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        "chat_str, expected_result",
        [
            ("\nsystem:\nname:\nAI \n content:\nfirst\n\nuser:\nsecond", [
                {'role': 'system', 'name': 'AI', 'content': 'first'}, {'role': 'user', 'content': 'second'}]),
            ("\nuser:\nname:\n\nperson\n content:\n", [
                {'role': 'user', 'name': 'person', 'content': ''}]),
            ("\nsystem:\nname:\n\n content:\nfirst", [
                {'role': 'system', 'content': 'name:\n\n content:\nfirst'}])
        ]
    )
    def test_success_parse_name_in_role_prompt(self, chat_str, expected_result):
        actual_result = parse_chat(chat_str)
        assert actual_result == expected_result

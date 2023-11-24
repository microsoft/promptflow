import pytest

from promptflow.contracts.multimedia import Image
from promptflow.tools.common import ChatAPIInvalidFunctions, validate_functions, process_function_call, \
    parse_chat, find_referenced_image_set, preprocess_template_string, convert_to_chat_list, ChatInputList


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
        "chat_str, images, expected_result",
        [
            ("system:\nthis is my function:\ndef hello", None, [
                {'role': 'system', 'content': 'this is my function:\ndef hello'}]),
            ("#system:\nthis is my ##function:\ndef hello", None, [
                {'role': 'system', 'content': 'this is my ##function:\ndef hello'}]),
            (" \n system:\nthis is my function:\ndef hello", None, [
                {'role': 'system', 'content': 'this is my function:\ndef hello'}]),
            (" \n # system:\nthis is my function:\ndef hello", None, [
                {'role': 'system', 'content': 'this is my function:\ndef hello'}]),
            ("user:\nhi\nassistant:\nanswer\nfunction:\nname:\nn\ncontent:\nc", None, [
                {'role': 'user', 'content': 'hi'},
                {'role': 'assistant', 'content': 'answer'},
                {'role': 'function', 'name': 'n', 'content': 'c'}]),
            ("#user :\nhi\n #assistant:\nanswer\n# function:\n##name:\nn\n##content:\nc", None, [
                {'role': 'user', 'content': 'hi'},
                {'role': 'assistant', 'content': 'answer'},
                {'role': 'function', 'name': 'n', 'content': 'c'}]),
            ("\nsystem:\nfirst\n\nsystem:\nsecond", None, [
                {'role': 'system', 'content': 'first'}, {'role': 'system', 'content': 'second'}]),
            ("\n#system:\nfirst\n\n#system:\nsecond", None, [
                {'role': 'system', 'content': 'first'}, {'role': 'system', 'content': 'second'}]),
            ("\n#system:\nfirst\n#assistant:\n#user:\nsecond", None, [
                {'role': 'system', 'content': 'first'},
                {'role': 'assistant', 'content': ''},
                {'role': 'user', 'content': 'second'}
            ]),
            # todo: enable this test case after we support image_url officially
            # ("#user:\ntell me about the images\nImage(1edf82c2)\nImage(9b65b0f4)", [
            #     Image("image1".encode()), Image("image2".encode(), "image/png", "https://image_url")], [
            #     {'role': 'user', 'content': [
            #         {'type': 'text', 'text': 'tell me about the images'},
            #         {'type': 'image_url', 'image_url': {'url': 'data:image/*;base64,aW1hZ2Ux'}},
            #         {'type': 'image_url', 'image_url': 'https://image_url'}]},
            # ])
        ]
    )
    def test_success_parse_role_prompt(self, chat_str, images, expected_result):
        actual_result = parse_chat(chat_str, images)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        "chat_str, expected_result",
        [
            ("\n#system:\n##name:\nAI \n content:\nfirst\n\n#user:\nsecond", [
                {'role': 'system', 'name': 'AI', 'content': 'first'}, {'role': 'user', 'content': 'second'}]),
            ("\nuser:\nname:\n\nperson\n content:\n", [
                {'role': 'user', 'name': 'person', 'content': ''}]),
            ("\nsystem:\nname:\n\n content:\nfirst", [
                {'role': 'system', 'content': 'name:\n\n content:\nfirst'}]),
            ("\nsystem:\nname:\n\n", [
                {'role': 'system', 'content': 'name:'}])
        ]
    )
    def test_parse_chat_with_name_in_role_prompt(self, chat_str, expected_result):
        actual_result = parse_chat(chat_str)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        "kwargs, expected_result",
        [
            ({}, set()),
            ({"image_1": Image("image1".encode()), "image_2": Image("image2".encode()), "t1": "text"}, {
                Image("image1".encode()), Image("image2".encode())
            }),
            ({"images": [Image("image1".encode()), Image("image2".encode())]}, {
                Image("image1".encode()), Image("image2".encode())
            }),
            ({"image_1": Image("image1".encode()), "image_2": Image("image1".encode())}, {
                Image("image1".encode())
            }),
            ({"images": {"image_1": Image("image1".encode()), "image_2": Image("image2".encode())}}, {
                Image("image1".encode()), Image("image2".encode())
            })
        ]
    )
    def test_find_referenced_image_set(self, kwargs, expected_result):
        actual_result = find_referenced_image_set(kwargs)
        assert actual_result == expected_result

    @pytest.mark.parametrize(
        "input_string, expected_output",
        [
            ("![image]({{img1}})", "\n{{img1}}\n"),
            ("![image]({{img1}})![image]({{img2}})", "\n{{img1}}\n\n{{img2}}\n"),
            ("No image here", "No image here"),
            ("![image]({{img1}}) Some text ![image]({{img2}})", "\n{{img1}}\n Some text \n{{img2}}\n"),
        ],
    )
    def test_preprocess_template_string(self, input_string, expected_output):
        actual_result = preprocess_template_string(input_string)
        assert actual_result == expected_output

    @pytest.mark.parametrize(
        "input_data, expected_output",
        [
            ({}, {}),
            ({"key": "value"}, {"key": "value"}),
            (["item1", "item2"], ChatInputList(["item1", "item2"])),
            ({"key": ["item1", "item2"]}, {"key": ChatInputList(["item1", "item2"])}),
            (["item1", ["nested_item1", "nested_item2"]],
             ChatInputList(["item1", ChatInputList(["nested_item1", "nested_item2"])])),
        ],
    )
    def test_convert_to_chat_list(self, input_data, expected_output):
        actual_result = convert_to_chat_list(input_data)
        assert actual_result == expected_output

# flake8: noqa: E501
from promptflow.tools.exception import (
    ChatAPIToolRoleInvalidFormat,
    ChatAPIAssistantRoleInvalidFormat,
)


VALIDATE_TOOLS_TEST_CASES = [
    (
        [
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "Get the current weather in a given location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA",
                            },
                            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                        },
                        "required": ["location"],
                    },
                },
            }
        ],
        "",
        True,
    ),
    ([], "tools cannot be an empty list", False),
    (["str"], "is not a dict. Here is a valid tool example", False),
    ([{"type1": "function", "function": "str"}], "does not have 'type' property", False),
    ([{"type": "function", "function": "str"}], "is not a dict. Here is a valid tool example", False),
    ([{"type": "function", "function": {"name": "func1"}}], "does not have 'parameters' property", False),
    (
        [{"type": "function", "function": {"name": "func1", "parameters": "param1"}}],
        "should be described as a JSON Schema object",
        False,
    ),
    (
        [{"type": "function", "function": {"name": "func1", "parameters": {"type": "int", "properties": {}}}}],
        "parameters 'type' should be 'object'",
        False,
    ),
    (
        [
            {
                "type": "function",
                "function": {"name": "func1", "parameters": {"type": "object", "properties": []}},
            }
        ],
        "should be described as a JSON Schema object",
        False,
    ),
]

CHAT_WITH_TOOLS_TEST_CASES = [
    (
        '# tool:\n## tool_call_id:\ncall_001\n## content:\n{"location": "San Francisco, CA", "temperature": "72", "unit": null}\n',
        [
            {
                "role": "tool",
                "tool_call_id": "call_001",
                "content": '{"location": "San Francisco, CA", "temperature": "72", "unit": null}',
            }
        ],
        True,
        "",
        "",
    ),
    (
        """
            # tool:
            ## tool_call_id:
            call_001
            ## content:
            {"location": "San Francisco, CA", "temperature": "72", "unit": null}

            # tool:
            ## tool_call_id:
            call_002
            ## content:
            {"location": "San Francisco, CA", "temperature": "72", "unit": null}

            # tool:
            ## tool_call_id:
            call_003
            ## content:
            {"location": "San Francisco, CA", "temperature": "72", "unit": null}
        """,
        [
            {
                "role": "tool",
                "tool_call_id": "call_001",
                "content": '{"location": "San Francisco, CA", "temperature": "72", "unit": null}',
            },
            {
                "role": "tool",
                "tool_call_id": "call_002",
                "content": '{"location": "San Francisco, CA", "temperature": "72", "unit": null}',
            },
            {
                "role": "tool",
                "tool_call_id": "call_003",
                "content": '{"location": "San Francisco, CA", "temperature": "72", "unit": null}',
            },
        ],
        True,
        "",
        "",
    ),
    (
        """
            # assistant:
            ## tool_calls:
            [{'id': 'call_001', 'function': {'arguments': '{"location": {"city": "San Francisco", "country": "USA"}, "unit": "metric"}', 'name': 'get_current_weather_py'}, 'type': 'function'}, {'id': 'call_002', 'function': {'arguments': '{"location": {"city": "Tokyo", "country": "Japan"}, "unit": "metric"}', 'name': 'get_current_weather_py'}, 'type': 'function'}, {'id': 'call_003', 'function': {'arguments': '{"location": {"city": "Paris", "country": "France"}, "unit": "metric"}', 'name': 'get_current_weather_py'}, 'type': 'function'}]
        """,
        [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_001",
                        "function": {
                            "arguments": '{"location": {"city": "San Francisco", "country": "USA"}, "unit": "metric"}',
                            "name": "get_current_weather_py",
                        },
                        "type": "function",
                    },
                    {
                        "id": "call_002",
                        "function": {
                            "arguments": '{"location": {"city": "Tokyo", "country": "Japan"}, "unit": "metric"}',
                            "name": "get_current_weather_py",
                        },
                        "type": "function",
                    },
                    {
                        "id": "call_003",
                        "function": {
                            "arguments": '{"location": {"city": "Paris", "country": "France"}, "unit": "metric"}',
                            "name": "get_current_weather_py",
                        },
                        "type": "function",
                    },
                ],
            }
        ],
        True,
        "",
        "",
    ),
    (
        """
            # system:
            Don't make assumptions about what values to plug into functions. Ask for clarification if a user request is ambiguous.

            # user:
            What's the weather like in San Francisco, Tokyo, and Paris?

            # assistant:
            ## tool_calls:
            [{'id': 'call_001', 'function': {'arguments': '{"location": {"city": "San Francisco", "country": "USA"}, "unit": "metric"}', 'name': 'get_current_weather_py'}, 'type': 'function'}, {'id': 'call_002', 'function': {'arguments': '{"location": {"city": "Tokyo", "country": "Japan"}, "unit": "metric"}', 'name': 'get_current_weather_py'}, 'type': 'function'}, {'id': 'call_003', 'function': {'arguments': '{"location": {"city": "Paris", "country": "France"}, "unit": "metric"}', 'name': 'get_current_weather_py'}, 'type': 'function'}]

            # tool:
            ## tool_call_id:
            call_001
            ## content:
            {"location": "San Francisco, CA", "temperature": "72", "unit": null}
            # tool:
            ## tool_call_id:
            call_002
            ## content:
            {"location": "Tokyo", "temperature": "72", "unit": null}
            # tool:
            ## tool_call_id:
            call_003
            ## content:
            {"location": "Paris", "temperature": "72", "unit": null}
        """,
        [
            {
                "role": "system",
                "content": "Don't make assumptions about what values to plug into functions. Ask for clarification if a user request is ambiguous.",
            },
            {
                "role": "user",
                "content": "What's the weather like in San Francisco, Tokyo, and Paris?",
            },
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_001",
                        "function": {
                            "arguments": '{"location": {"city": "San Francisco", "country": "USA"}, "unit": "metric"}',
                            "name": "get_current_weather_py",
                        },
                        "type": "function",
                    },
                    {
                        "id": "call_002",
                        "function": {
                            "arguments": '{"location": {"city": "Tokyo", "country": "Japan"}, "unit": "metric"}',
                            "name": "get_current_weather_py",
                        },
                        "type": "function",
                    },
                    {
                        "id": "call_003",
                        "function": {
                            "arguments": '{"location": {"city": "Paris", "country": "France"}, "unit": "metric"}',
                            "name": "get_current_weather_py",
                        },
                        "type": "function",
                    },
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_001",
                "content": '{"location": "San Francisco, CA", "temperature": "72", "unit": null}',
            },
            {
                "role": "tool",
                "tool_call_id": "call_002",
                "content": '{"location": "Tokyo", "temperature": "72", "unit": null}',
            },
            {
                "role": "tool",
                "tool_call_id": "call_003",
                "content": '{"location": "Paris", "temperature": "72", "unit": null}',
            },
        ],
        True,
        "",
        "",
    ),
    (
        """
            # assistant:
            ## tool_calls:
        """,
        [],
        False,
        "Failed to parse assistant role prompt with tool_calls",
        ChatAPIAssistantRoleInvalidFormat,
    ),
    (
        """
            # tool:
            ## tool_call_id:
            call_001
            ## content:
            {"location": "San Francisco, CA", "temperature": "72", "unit": null}
            # tool:
            ## tool_call_id:
        """,
        [],
        False,
        "Failed to parse tool role prompt.",
        ChatAPIToolRoleInvalidFormat,
    ),
]

ASSISTANT_WITH_TOOL_CALLS_TEST_CASES = [
    ("""
        ## tool_calls:
        """, "", "Failed to parse assistant role prompt with tool_calls", False),
    ("""
        ## tool_calls:
        tool_calls_str
        """, "", "Failed to parse assistant role prompt with tool_calls", False),
    ("""
        ## tool_calls:
        [{"id": "tool_call_id", "type": "function", "function": {"name": "func1", "arguments": {}}}]
        """, [{"id": "tool_call_id", "type": "function", "function": {"name": "func1", "arguments": {}}}], "", True),
    ("""
        ## tool_calls:

        [{"id": "tool_call_id", "type": "function", "function": {"name": "func1", "arguments": {}}}]
        """, [{"id": "tool_call_id", "type": "function", "function": {"name": "func1", "arguments": {}}}], "", True),
    ("""
        ## tool_calls:[{"id": "tool_call_id", "type": "function", "function": {"name": "func1", "arguments": {}}}]
        """, [{"id": "tool_call_id", "type": "function", "function": {"name": "func1", "arguments": {}}}], "", True),
    ("""
        ## tool_calls:
        [{
            "id": "tool_call_id",
            "type": "function",
            "function": {"name": "func1", "arguments": {}}
        }]
        """, [{"id": "tool_call_id", "type": "function", "function": {"name": "func1", "arguments": {}}}], "", True),
    ("""
        ## tool_calls:
        [{
            "id": "tool_call_id", "type": "function",
                "function": {"name": "func1", "arguments": {}}
        }]
        """, [{"id": "tool_call_id", "type": "function", "function": {"name": "func1", "arguments": {}}}], "", True),
]
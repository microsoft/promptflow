import pytest

from promptflow.parallel._config.parser import _parse_prefixed_args


def test_parse_prefixed_args_value_with_equals():
    # Base64 "Hello World" ends with '=' padding
    parsed = _parse_prefixed_args(
        ["--pf_input_token=SGVsbG8gV29ybGQ="],
        "--pf_input_",
    )
    assert parsed == {"token": "SGVsbG8gV29ybGQ="}


def test_parse_prefixed_args_url_query_string():
    parsed = _parse_prefixed_args(
        ["--pf_input_url=https://example.com?a=1&b=2"],
        "--pf_input_",
    )
    assert parsed["url"] == "https://example.com?a=1&b=2"


def test_parse_prefixed_args_space_separated():
    parsed = _parse_prefixed_args(
        ["--pf_input_arg2", "arg2"],
        "--pf_input_",
    )
    assert parsed == {"arg2": "arg2"}

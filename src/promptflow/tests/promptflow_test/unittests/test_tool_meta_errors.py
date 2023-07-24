from pathlib import Path

import pytest

from promptflow.utils.generate_tool_meta_utils import (
    JinjaParsingError,
    MultipleToolsDefined,
    NoToolDefined,
    PythonParsingError,
    ReservedVariableCannotBeUsed,
    generate_prompt_meta,
    generate_python_meta,
)

TEST_ROOT = Path(__file__).parent.parent.parent
TOOLS_ROOT = TEST_ROOT / "test_configs/wrong_tools"


@pytest.mark.unittest
class TestToolMetaErrors:
    @pytest.mark.parametrize(
        "content, error_code, message",
        [
            ("zzz", PythonParsingError, "Parsing python got exception: name 'zzz' is not defined"),
            ("# Nothing", NoToolDefined, "No tool found in the python script."),
            ("multiple_tools.py", MultipleToolsDefined, "Expected 1 but collected 2 tools: tool1, tool2."),
        ],
    )
    def test_custom_python_meta(self, content, error_code, message) -> None:
        if content.endswith(".py"):
            with open(TOOLS_ROOT / content, "r") as f:
                code = f.read()
        else:
            code = content
        with pytest.raises(Exception) as ex:
            generate_python_meta("some_tool", code)
        assert message == ex.value.args[0]
        assert message == str(ex.value)
        assert error_code == ex.value.__class__

    @pytest.mark.parametrize(
        "content, error_code, message",
        [
            (
                "{% zzz",
                JinjaParsingError,
                "Parsing jinja got exception: Encountered unknown tag 'zzz'.",
            ),
            (
                "no_end.jinja2",
                JinjaParsingError,
                "Parsing jinja got exception: Unexpected end of template. Jinja was looking for the following tags: "
                "'endfor' or 'else'. The innermost block that needs to be closed is 'for'.",
            ),
            (
                "{{max_tokens}}",
                ReservedVariableCannotBeUsed,
                "Parsing jinja got exception: Variable name max_tokens is reserved by LLM. Please change another name.",
            ),
        ],
    )
    def test_custom_llm_meta(self, content, error_code, message) -> None:
        if content.endswith(".jinja2"):
            with open(TOOLS_ROOT / content, "r") as f:
                code = f.read()
        else:
            code = content
        with pytest.raises(Exception) as ex:
            generate_prompt_meta("some_tool", code)
        assert message == ex.value.args[0]
        assert message == str(ex.value)
        assert error_code == ex.value.__class__

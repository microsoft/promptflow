import os
import re
import sys
from multiprocessing import Pool
from pathlib import Path
from unittest.mock import patch

import pytest

from promptflow._core.tool_meta_generator import (
    JinjaParsingError,
    MultipleToolsDefined,
    NoToolDefined,
    PythonLoadError,
    PythonParsingError,
    ReservedVariableCannotBeUsed,
    generate_prompt_meta,
    generate_python_meta,
    generate_tool_meta_dict_by_file,
)
from promptflow._utils.exception_utils import ExceptionPresenter

from ...utils import FLOW_ROOT, load_json

TEST_ROOT = Path(__file__).parent.parent.parent.parent
TOOLS_ROOT = TEST_ROOT / "test_configs/wrong_tools"


def cd_and_run(working_dir, source_path, tool_type):
    os.chdir(working_dir)
    sys.path.insert(0, working_dir)
    try:
        return generate_tool_meta_dict_by_file(source_path, tool_type)
    except Exception as e:
        return f"({e.__class__.__name__}) {e}"


def cd_and_run_with_read_text_error(working_dir, source_path, tool_type):
    def mock_read_text_error(self: Path, *args, **kwargs):
        raise Exception("Mock read text error.")

    os.chdir(working_dir)
    sys.path.insert(0, working_dir)
    try:
        with patch("promptflow._core.tool_meta_generator.Path.read_text", new=mock_read_text_error):
            return generate_tool_meta_dict_by_file(source_path, tool_type)
    except Exception as e:
        return f"({e.__class__.__name__}) {e}"


def cd_and_run_with_bad_function_interface(working_dir, source_path, tool_type):
    def mock_function_to_interface(*args, **kwargs):
        raise Exception("Mock function to interface error.")

    os.chdir(working_dir)
    sys.path.insert(0, working_dir)
    try:
        with patch("promptflow._core.tool_meta_generator.function_to_interface", new=mock_function_to_interface):
            return generate_tool_meta_dict_by_file(source_path, tool_type)
    except Exception as e:
        return f"({e.__class__.__name__}) {e}"


def generate_tool_meta_dict_by_file_with_cd(wd, tool_path, tool_type, func):
    with Pool(1) as pool:
        return pool.apply(func, (wd, tool_path, tool_type))


@pytest.mark.unittest
class TestToolMetaUtils:
    @pytest.mark.parametrize(
        "flow_dir, tool_path, tool_type",
        [
            ("prompt_tools", "summarize_text_content_prompt.jinja2", "prompt"),
            ("prompt_tools", "summarize_text_content_prompt.jinja2", "llm"),
            ("script_with_import", "dummy_utils/main.py", "python"),
            ("script_with___file__", "script_with___file__.py", "python"),
        ],
    )
    def test_generate_tool_meta_dict_by_file(self, flow_dir, tool_path, tool_type):
        wd = str((FLOW_ROOT / flow_dir).resolve())
        meta_dict = generate_tool_meta_dict_by_file_with_cd(wd, tool_path, tool_type, cd_and_run)
        assert isinstance(meta_dict, dict), "Call cd_and_run failed:\n" + meta_dict
        target_file = (Path(wd) / tool_path).with_suffix(".meta.json")
        expected_dict = load_json(target_file)
        if tool_type == "llm":
            expected_dict["type"] = "llm"  # We use prompt as default for jinja2
        assert meta_dict == expected_dict

    @pytest.mark.parametrize(
        "flow_dir, tool_path, tool_type, func, msg_pattern",
        [
            pytest.param(
                "prompt_tools",
                "summarize_text_content_prompt.jinja2",
                "python",
                cd_and_run,
                r"\(PythonLoaderNotFound\) Failed to load python file '.*summarize_text_content_prompt.jinja2'. "
                r"Please make sure it is a valid .py file.",
                id="PythonLoaderNotFound",
            ),
            pytest.param(
                "script_with_import",
                "fail.py",
                "python",
                cd_and_run,
                r"\(PythonLoadError\) Failed to load python module from file '.*fail.py': "
                r"\(ModuleNotFoundError\) No module named 'aaa'",
                id="PythonLoadError",
            ),
            pytest.param(
                "simple_flow_with_python_tool",
                "divide_num.py",
                "python",
                cd_and_run_with_bad_function_interface,
                r"\(BadFunctionInterface\) Parse interface for tool 'divide_num' failed: "
                r"\(Exception\) Mock function to interface error.",
                id="BadFunctionInterface",
            ),
            pytest.param(
                "script_with_import",
                "aaa.py",
                "python",
                cd_and_run,
                r"\(MetaFileNotFound\) Generate tool meta failed for python tool. "
                r"Meta file '.*aaa.py' can not be found.",
                id="MetaFileNotFound",
            ),
            pytest.param(
                "simple_flow_with_python_tool",
                "divide_num.py",
                "python",
                cd_and_run_with_read_text_error,
                r"\(MetaFileReadError\) Generate tool meta failed for python tool. "
                r"Read meta file '.*divide_num.py' failed: \(Exception\) Mock read text error.",
                id="MetaFileReadError",
            ),
            pytest.param(
                "simple_flow_with_python_tool",
                "divide_num.py",
                "action",
                cd_and_run,
                r"\(NotSupported\) Generate tool meta failed. The type 'action' is currently unsupported. "
                r"Please choose from available types: python,llm,prompt and try again.",
                id="NotSupported",
            ),
        ],
    )
    def test_generate_tool_meta_dict_by_file_exception(self, flow_dir, tool_path, tool_type, func, msg_pattern):
        wd = str((FLOW_ROOT / flow_dir).resolve())
        ret = generate_tool_meta_dict_by_file_with_cd(wd, tool_path, tool_type, func)
        assert isinstance(ret, str), "Call cd_and_run should fail but succeeded:\n" + str(ret)
        assert re.match(msg_pattern, ret)

    @pytest.mark.parametrize(
        "content, error_code, message",
        [
            pytest.param(
                "zzz",
                PythonParsingError,
                "Failed to load python module. Python parsing failed: (NameError) name 'zzz' is not defined",
                id="PythonParsingError_NameError",
            ),
            pytest.param(
                "# Nothing",
                NoToolDefined,
                "The number of tools defined is illegal. No tool found in the python script. "
                "Please make sure you have one and only one tool definition in your script.",
                id="NoToolDefined",
            ),
            pytest.param(
                "multiple_tools.py",
                MultipleToolsDefined,
                "The number of tools defined is illegal. Expected 1 but collected 2 tools: tool1, tool2. "
                "Please make sure you have one and only one tool definition in your script.",
                id="MultipleToolsDefined",
            ),
            pytest.param(
                "{% zzz",
                PythonParsingError,
                "Failed to load python module. Python parsing failed: "
                "(SyntaxError) invalid syntax (<string>, line 1)",
                id="PythonParsingError_SyntaxError",
            ),
        ],
    )
    def test_custom_python_meta(self, content, error_code, message) -> None:
        if content.endswith(".py"):
            source = TOOLS_ROOT / content
            with open(source, "r") as f:
                code = f.read()
        else:
            code = content
            source = None
        with pytest.raises(error_code) as ex:
            generate_python_meta("some_tool", code, source)
        assert message == str(ex.value)

    @pytest.mark.parametrize(
        "content, error_code, message",
        [
            pytest.param(
                "{% zzz",
                JinjaParsingError,
                "Generate tool meta failed for llm tool. Jinja parsing failed: "
                "(TemplateSyntaxError) Encountered unknown tag 'zzz'.",
                id="JinjaParsingError_Code",
            ),
            pytest.param(
                "no_end.jinja2",
                JinjaParsingError,
                "Generate tool meta failed for llm tool. Jinja parsing failed: "
                "(TemplateSyntaxError) Unexpected end of template. Jinja was looking for the following tags: "
                "'endfor' or 'else'. The innermost block that needs to be closed is 'for'.",
                id="JinjaParsingError_File",
            ),
            pytest.param(
                "{{max_tokens}}",
                ReservedVariableCannotBeUsed,
                "Generate tool meta failed for llm tool. Jinja parsing failed: "
                "Variable name 'max_tokens' is reserved name by llm tools, please change to another name.",
                id="ReservedVariableCannotBeUsed",
            ),
        ],
    )
    def test_custom_llm_meta(self, content, error_code, message) -> None:
        if content.endswith(".jinja2"):
            with open(TOOLS_ROOT / content, "r") as f:
                code = f.read()
        else:
            code = content
        with pytest.raises(error_code) as ex:
            generate_prompt_meta("some_tool", code)
        assert message == str(ex.value)

    @pytest.mark.parametrize(
        "content, error_code, message",
        [
            pytest.param(
                "{% zzz",
                JinjaParsingError,
                "Generate tool meta failed for prompt tool. Jinja parsing failed: "
                "(TemplateSyntaxError) Encountered unknown tag 'zzz'.",
                id="JinjaParsingError_Code",
            ),
            pytest.param(
                "no_end.jinja2",
                JinjaParsingError,
                "Generate tool meta failed for prompt tool. Jinja parsing failed: "
                "(TemplateSyntaxError) Unexpected end of template. Jinja was looking for the following tags: "
                "'endfor' or 'else'. The innermost block that needs to be closed is 'for'.",
                id="JinjaParsingError_File",
            ),
            pytest.param(
                "{{template}}",  # Note that only template is reserved, while llm tool has more reserved variables.
                ReservedVariableCannotBeUsed,
                "Generate tool meta failed for prompt tool. Jinja parsing failed: "
                "Variable name 'template' is reserved name by prompt tools, please change to another name.",
                id="ReservedVariableCannotBeUsed",
            ),
        ],
    )
    def test_custom_prompt_meta(self, content, error_code, message) -> None:
        if content.endswith(".jinja2"):
            with open(TOOLS_ROOT / content, "r") as f:
                code = f.read()
        else:
            code = content
        with pytest.raises(error_code) as ex:
            generate_prompt_meta("some_tool", code, prompt_only=True)
        assert message == str(ex.value)


@pytest.mark.unittest
class TestPythonLoadError:
    def test_additional_info(self):
        source = TOOLS_ROOT / "load_error.py"
        with open(source, "r") as f:
            code = f.read()
        with pytest.raises(PythonLoadError) as ex:
            generate_python_meta("some_tool", code, source)

        additional_info = ExceptionPresenter.create(ex.value).to_dict().get("additionalInfo")
        assert len(additional_info) == 1

        info_0 = additional_info[0]
        assert info_0["type"] == "UserCodeStackTrace"
        info_0_value = info_0["info"]
        assert info_0_value.get("type") == "ZeroDivisionError"
        assert info_0_value.get("message") == "division by zero"
        assert re.match(r".*load_error.py", info_0_value["filename"])
        assert info_0_value.get("lineno") == 3
        assert info_0_value.get("name") == "<module>"
        assert re.search(
            r"Traceback \(most recent call last\):\n"
            r'  File ".*load_error.py", line .*, in <module>\n'
            r"    1 / 0\n"
            r"(.*\n)?"  # Python >= 3.11 add extra line here like a pointer.
            r"ZeroDivisionError: division by zero\n",
            info_0_value.get("traceback"),
        )

    def test_additional_info_for_empty_inner_error(self):
        ex = PythonLoadError(message_format="Test empty error")
        additional_info = ExceptionPresenter.create(ex).to_dict().get("additionalInfo")
        assert additional_info is None

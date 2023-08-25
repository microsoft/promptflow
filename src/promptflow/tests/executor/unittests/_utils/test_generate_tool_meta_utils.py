import os
import re
import sys
from multiprocessing import Pool
from pathlib import Path

import pytest

from promptflow._core.tool_meta_generator import PythonLoadError, generate_python_meta, generate_tool_meta_dict_by_file
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
        return str(e)


def generate_tool_meta_dict_by_file_with_cd(wd, tool_path, tool_type):
    with Pool(1) as pool:
        return pool.apply(cd_and_run, (wd, tool_path, tool_type))


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
        meta_dict = generate_tool_meta_dict_by_file_with_cd(wd, tool_path, tool_type)
        assert isinstance(meta_dict, dict), "Call cd_and_run failed:\n" + meta_dict
        target_file = (Path(wd) / tool_path).with_suffix(".meta.json")
        expected_dict = load_json(target_file)
        if tool_type == "llm":
            expected_dict["type"] = "llm"  # We use prompt as default for jinja2
        assert meta_dict == expected_dict

    @pytest.mark.parametrize(
        "flow_dir, tool_path, tool_type, msg",
        [
            (
                "prompt_tools",
                "summarize_text_content_prompt.jinja2",
                "python",
                "summarize_text_content_prompt.jinja2', please make sure it is a valid .py file.",
            ),
            (
                "script_with_import",
                "fail.py",
                "python",
                "Failed to load python module from file",
            ),
        ],
    )
    def test_generate_tool_meta_dict_by_file_exception(self, flow_dir, tool_path, tool_type, msg):
        wd = str((FLOW_ROOT / flow_dir).resolve())
        ret = generate_tool_meta_dict_by_file_with_cd(wd, tool_path, tool_type)
        assert isinstance(ret, str), "Call cd_and_run should fail but succeeded:\n" + str(ret)
        assert msg in ret


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
            r"ZeroDivisionError: division by zero\n",
            info_0_value.get("traceback"),
        )

    def test_additional_info_for_empty_inner_error(self):
        ex = PythonLoadError("Test empty error")
        additional_info = ExceptionPresenter.create(ex).to_dict().get("additionalInfo")
        assert additional_info is None

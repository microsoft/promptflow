import os
import sys
from multiprocessing import Pool
from pathlib import Path

import pytest

from promptflow._utils.generate_tool_meta_utils import generate_tool_meta_dict_by_file

from ...utils import FLOW_ROOT, load_json


def cd_and_run(working_dir, source_path, tool_type):
    os.chdir(working_dir)
    sys.path.insert(0, working_dir)
    try:
        return generate_tool_meta_dict_by_file(source_path, tool_type)
    except Exception as e:
        return str(e)


@pytest.mark.unittest
class TestToolMetaUtils:
    @pytest.mark.parametrize(
        "flow_dir, tool_path, tool_type",
        [
            ("prompt_tools", "summarize_text_content_prompt.jinja2", "prompt"),
            ("prompt_tools", "summarize_text_content_prompt.jinja2", "llm"),
            ("script_with_import", "dummy_utils/main.py", "python"),
        ],
    )
    def test_generate_tool_meta_dict_by_file(self, flow_dir, tool_path, tool_type):
        with Pool(1) as pool:
            wd = str((FLOW_ROOT / flow_dir).resolve())
            meta_dict = pool.apply(cd_and_run, (wd, tool_path, tool_type))
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
                "Failed to load python file 'summarize_text_content_prompt.jinja2',"
                " please make sure it is a valid .py file.",
            ),
            (
                "script_with_import",
                "fail.py",
                "python",
                "Failed to load python module from file fail.py, reason: No module named 'aaa'.",
            ),
        ],
    )
    def test_generate_tool_meta_dict_by_file_exception(self, flow_dir, tool_path, tool_type, msg):
        with Pool(1) as pool:
            wd = str((FLOW_ROOT / flow_dir).resolve())
            ret = pool.apply(cd_and_run, (wd, tool_path, tool_type))
            assert isinstance(ret, str), "Call cd_and_run should fail but succeeded:\n" + str(ret)
            assert msg in ret

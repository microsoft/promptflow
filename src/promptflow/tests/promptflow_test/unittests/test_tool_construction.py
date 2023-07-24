import importlib
import json
import subprocess
from pathlib import Path
from tempfile import mkdtemp

import pytest

from promptflow.connections import AzureOpenAIConnection, BingConnection, OpenAIConnection
from promptflow.core.tool import dump
from promptflow.scripts.dump_builtin_tool import dump_tool_to_meta
from promptflow.scripts.dump_connection import dump_connection_to_meta
from promptflow.tools import AzureOpenAI, OpenAI
from promptflow.tools.bing import Bing
from promptflow.utils.generate_tool_meta_utils import generate_prompt_meta, generate_python_meta
from promptflow.utils.tool_utils import create_function_source
from promptflow_test.utils import assert_json_equal, assert_json_file_equal, load_json

TEST_ROOT = Path(__file__).parent.parent.parent
tool_cases = [
    ("common_tools/try_import.py", "common_tools/try_import.json", None),
    ("qa_with_bing/qa.jinja2", "qa_with_bing/qa_prompt.json", None),
    ("qa_with_bing/qa.jinja2", "qa_with_bing/qa_llm.json", "llm"),
]


@pytest.mark.e2etest
class TestToolConstruction:
    @pytest.mark.parametrize(
        "tool_file, expected_meta_file, tool_type",
        tool_cases,
    )
    def test_tool_meta_cli_output_mode(self, tool_file, expected_meta_file, tool_type):
        working_dir = Path(TEST_ROOT / "test_configs/e2e_samples")
        output_file = Path(mkdtemp()) / "meta.json"
        cmd = f"python -m promptflow._cli.tools -f {tool_file} -o {output_file} -m output"
        cmd += f" -wd {working_dir}"
        if tool_type is not None:
            cmd += f" -t {tool_type}"
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            raise RuntimeError(f"Failed to run command, stderr={p.stderr.decode()}")
        assert_json_file_equal(output_file, working_dir / expected_meta_file)

    def test_tool_meta_cli_append_mode(
        self,
    ):
        working_dir = Path(TEST_ROOT / "test_configs/e2e_samples")
        output_file = Path(mkdtemp()) / "meta.json"
        expected = {"package": {}, "code": {}}
        for tool_file, expected_meta_file, tool_type in tool_cases:
            cmd = f"python -m promptflow._cli.tools -f {tool_file} -o {output_file} -wd {working_dir}"
            if tool_type is not None:
                cmd += f" -t {tool_type}"
            p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode != 0:
                raise RuntimeError(f"Failed to run command, stderr={p.stderr.decode()}")
            expected["code"][tool_file] = load_json(working_dir / expected_meta_file)
        output_tool_json = load_json(output_file)
        assert_json_equal(output_tool_json, expected)

    @pytest.mark.parametrize(
        "tool_file, tool_func_name",
        [
            ("class_globals.py", "class_globals_tool"),
        ],
    )
    def test_valid_tool_metas(self, tool_file, tool_func_name):
        with open(TEST_ROOT / "test_configs/e2e_samples/common_tools" / tool_file, "r") as fin:
            code = fin.read()
        dumped_content = json.loads(generate_python_meta("dummy", code))
        assert dumped_content["function"] == tool_func_name

    def test_custom_tool_meta(self) -> None:
        from test_configs.tools.extract import extract

        # 1. test example_tool.json
        dumped_content1 = json.loads(dump(extract))
        code = open(TEST_ROOT / "test_configs/tools/extract.py", "r").read()
        dumped_content2 = json.loads(generate_python_meta("extract", code))
        dumped_content2["code"] = dumped_content1["code"].replace("\n\ndef", "def")
        expected_content = {
            "name": "extract",
            "type": "python",
            "inputs": {"result": {"type": ["object"]}, "search_engine": {"type": ["object"]}},
            "code": "from typing import List, Mapping, Dict\n"
            "from promptflow import tool\n\n"
            "@tool\n"
            "def extract(result, search_engine):\n"
            '    if search_engine == "Bing":\n'
            "        return {\n"
            '            "title": result["webPages"]["value"][0]["name"],\n'
            '            "snippet": '
            'result["webPages"]["value"][0]["snippet"]}\n'
            "    else:\n"
            '        raise ValueError("search engine {} is not '
            'supported".format(search_engine))\n',
            "function": "extract",
        }
        for k, v in expected_content.items():
            assert v == dumped_content1[k], f"key {k} is not equal for constructed meta"
            assert v == dumped_content2[k], f"key {k} is not equal for generated meta"

    def test_connection_in_custom_tool_meta(self) -> None:
        from test_configs.tools.extract_with_connection import extract

        # 1. test example_tool.json
        dumped_inputs1 = json.loads(dump(extract))["inputs"]
        code = open(TEST_ROOT / "test_configs/tools/extract_with_connection.py", "r").read()
        dumped_inputs2 = json.loads(generate_python_meta("extract", code))["inputs"]
        expected_content = {
            "bing_conn": {"type": ["BingConnection", "CustomConnection"]},
            "result": {"type": ["object"]},
            "search_engine": {"type": ["string"]},
        }
        for k, v in expected_content.items():
            assert v == dumped_inputs1[k], f"key {k} is not equal for constructed meta"
            assert v == dumped_inputs2[k], f"key {k} is not equal for generated meta"

    def test_union_in_custom_tool_meta(self) -> None:
        from test_configs.tools.non_connection_union import extract

        # The union annotation of bing_conn includes non connection type, so we gen it as object
        dumped_inputs1 = json.loads(dump(extract))["inputs"]
        code = open(TEST_ROOT / "test_configs/tools/non_connection_union.py", "r").read()
        dumped_inputs2 = json.loads(generate_python_meta("extract", code))["inputs"]
        expected_content = {
            "bing_conn": {"type": ["object"]},
            "result": {"type": ["object"]},
            "search_engine": {"type": ["string"]},
        }
        for k, v in expected_content.items():
            assert v == dumped_inputs1[k], f"key {k} is not equal for constructed meta"
            assert v == dumped_inputs2[k], f"key {k} is not equal for generated meta"

    def test_builtin_tool_meta(self) -> None:
        bing_api = Bing.from_config(BingConnection(api_key=None))
        dumped_content = json.loads(dump(bing_api.search, name="my tool", description="my description"))
        expected_content = {
            "class_name": "Bing",
            "function": "search",
            "inputs": {
                "answerCount": {"default": "", "type": ["int"]},
                "cc": {"default": "", "type": ["string"]},
                "connection": {"type": ["BingConnection"]},
                "count": {"default": "10", "type": ["int"]},
                "freshness": {"default": "", "type": ["string"]},
                "mkt": {"default": "", "type": ["string"]},
                "offset": {"default": "0", "type": ["int"]},
                "promote": {"default": "[]", "type": ["list"]},
                "query": {"type": ["string"]},
                "responseFilter": {"default": "[]", "type": ["list"]},
                "safesearch": {"default": "Moderate", "type": ["string"]},
                "setLang": {"default": "en", "type": ["string"]},
                "textDecorations": {"default": "False", "type": ["bool"]},
                "textFormat": {"default": "Raw", "type": ["string"]},
            },
            "module": "promptflow.tools.bing",
            "name": "my tool",
            "description": "my description",
            "type": "python",
            "is_builtin": True,
            "stage": "test",
        }
        assert dumped_content == expected_content

    def test_builtin_tool_meta_from_file(self) -> None:
        py_module = importlib.import_module("test_configs.tools.example_builtin_tool")
        dumped_content = json.loads(dump_tool_to_meta("my tool", py_module))
        expected_content = {
            "name": "my tool",
            "type": "python",
            "inputs": {
                "my_connection": {"type": ["BingConnection"]},
                "query": {
                    "type": ["string"],
                },
                "count": {"type": ["int"], "default": "10"},
            },
            "module": "test_configs.tools.example_builtin_tool",
            "class_name": "MyBing",
            "function": "search",
            "is_builtin": True,
            "stage": "test",
        }
        assert dumped_content == expected_content

    def test_aoai_inputs_meta(self) -> None:
        aoai_provider = AzureOpenAI.from_config(AzureOpenAIConnection(api_key=None, api_base=None))
        dumped_content = json.loads(dump(aoai_provider.completion))["inputs"]
        expected_content = {
            "connection": {"type": ["AzureOpenAIConnection"]},
            "best_of": {"default": "1", "type": ["int"]},
            "echo": {"default": "False", "type": ["bool"]},
            "deployment_name": {"type": ["string"]},
            "frequency_penalty": {"default": "0", "type": ["double"]},
            "logit_bias": {"default": "{}", "type": ["object"]},
            "logprobs": {"default": "", "type": ["int"]},
            "max_tokens": {"default": "16", "type": ["int"]},
            "n": {"default": "1", "type": ["int"]},
            "presence_penalty": {"default": "0", "type": ["double"]},
            "prompt": {"type": ["prompt_template"]},
            "stop": {"default": "", "type": ["list"]},
            "stream": {"default": "False", "type": ["bool"]},
            "suffix": {"default": "", "type": ["string"]},
            "temperature": {"default": "1.0", "type": ["double"]},
            "top_p": {"default": "1.0", "type": ["double"]},
            "user": {"default": "", "type": ["string"]},
        }
        assert dumped_content == expected_content

    def test_openai_inputs_meta(self) -> None:
        openai_provider = OpenAI.from_config(OpenAIConnection(api_key=None))
        dumped_content = json.loads(dump(openai_provider.completion))["inputs"]
        expected_content = {
            "best_of": {"default": "1", "type": ["int"]},
            "connection": {"type": ["OpenAIConnection"]},
            "echo": {"default": "False", "type": ["bool"]},
            "frequency_penalty": {"default": "0", "type": ["double"]},
            "logit_bias": {"default": "{}", "type": ["object"]},
            "logprobs": {"default": "", "type": ["int"]},
            "max_tokens": {"default": "16", "type": ["int"]},
            "model": {
                "default": "text-davinci-003",
                "enum": [
                    "text-davinci-001",
                    "text-davinci-002",
                    "text-davinci-003",
                    "text-curie-001",
                    "text-babbage-001",
                    "text-ada-001",
                    "code-cushman-001",
                    "code-davinci-002",
                ],
                "type": ["string"],
            },
            "n": {"default": "1", "type": ["int"]},
            "presence_penalty": {"default": "0", "type": ["double"]},
            "prompt": {"type": ["prompt_template"]},
            "stop": {"default": "", "type": ["list"]},
            "stream": {"default": "False", "type": ["bool"]},
            "suffix": {"default": "", "type": ["string"]},
            "temperature": {"default": "1.0", "type": ["double"]},
            "top_p": {"default": "1.0", "type": ["double"]},
            "user": {"default": "", "type": ["string"]},
        }
        assert dumped_content == expected_content

    def test_prompt_tool_meta(self) -> None:
        # 3. test prompt meta
        prompt = """{# This is a answer tool##. #} {# unused #}
You are a chatbot having a conversation with a human.
Given the following extracted parts of a long document and a query, create a final answer with references ("SOURCES").
If you don't know the answer, just say that you don't know. Don't try to make up an answer.
ALWAYS return a "SOURCES" part in your answer.
{{contexts}}
Human: {{query}}"""
        dumped_content = json.loads(generate_prompt_meta("answer", prompt))
        expected_content = {
            "name": "answer",
            "type": "llm",
            "description": "This is a answer tool##.",
            "code": "{# This is a answer tool##. #} {# unused #}\n"
            "You are a chatbot having a conversation with a human.\n"
            "Given the following extracted parts of a long document and a query, "
            'create a final answer with references ("SOURCES").\n'
            "If you don't know the answer, just say that you don't know. Don't "
            "try to make up an answer.\n"
            'ALWAYS return a "SOURCES" part in your answer.\n'
            "{{contexts}}\n"
            "Human: {{query}}",
            "inputs": {"contexts": {"type": ["string"]}, "query": {"type": ["string"]}},
        }
        assert dumped_content == expected_content

    def test_prompt_tool_inpus_order(self) -> None:
        prompt = """{{in1}}
{{in2}}
{{in3}}"""
        meta = json.loads(generate_prompt_meta("test", prompt))
        inputs = list(meta["inputs"].keys())
        assert inputs[0] == "in1"
        assert inputs[1] == "in2"
        assert inputs[2] == "in3"

    def test_function_resource(self):
        from test_configs.example_py.custom_tool_with_connection import consume_connection

        source = create_function_source(consume_connection)
        assert (
            source
            == """from typing import List, Mapping, Dict
from promptflow import tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.connections import BingConnection as BingConn
from promptflow.tools.aoai import AzureOpenAI
from promptflow.tools.aoai import completion

def do_nothing():
    assert completion


@tool
def consume_connection(
    question: str, aoai: AzureOpenAIConnection, bing: BingConn
):
    do_nothing()
    assert isinstance(aoai, AzureOpenAIConnection)
    assert isinstance(bing, BingConn)
    return AzureOpenAI(aoai).completion(question, "text-ada-001")
"""
        )

    def test_connection_meta(self):
        connections = dump_connection_to_meta("promptflow.connections")
        print(connections)
        assert connections[0].serialize() == {
            "connectionCategory": "CustomKeys",
            "flowValueType": "AzureContentSafetyConnection",
            "connectionType": "AzureContentSafety",
            "module": "promptflow.connections",
            "configSpecs": [
                {"name": "api_key", "displayName": "Api Key", "configValueType": "Secret", "isOptional": False},
                {"name": "endpoint", "displayName": "Endpoint", "configValueType": "String", "isOptional": False},
                {
                    "name": "api_version",
                    "displayName": "Api Version",
                    "configValueType": "String",
                    "defaultValue": "2023-04-30-preview",
                    "isOptional": False,
                },
            ],
        }

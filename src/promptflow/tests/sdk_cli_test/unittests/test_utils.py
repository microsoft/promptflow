# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import mock
import pandas as pd
import pytest

from promptflow._cli._params import AppendToDictAction
from promptflow._cli._utils import (
    _build_sorted_column_widths_tuple_list,
    _calculate_column_widths,
    list_of_dict_to_nested_dict,
)
from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR
from promptflow._sdk._errors import GenerateFlowToolsJsonError
from promptflow._sdk._utils import (
    _generate_connections_dir,
    decrypt_secret_value,
    encrypt_secret_value,
    generate_flow_tools_json,
    override_connection_config_with_environment_variable,
    refresh_connections_dir,
    resolve_connections_environment_variable_reference,
    snake_to_camel,
)
from promptflow._utils.load_data import load_data

TEST_ROOT = Path(__file__).parent.parent.parent
CONNECTION_ROOT = TEST_ROOT / "test_configs/connections"


@pytest.mark.unittest
class TestUtils:
    def test_encrypt_decrypt_value(self):
        test_value = "test"
        encrypted = encrypt_secret_value(test_value)
        assert decrypt_secret_value("mock", encrypted) == test_value

    def test_snake_to_camel(self):
        assert snake_to_camel("test_snake_case") == "TestSnakeCase"
        assert snake_to_camel("TestSnakeCase") == "TestSnakeCase"

    def test_sqlite_retry(self, capfd) -> None:
        from sqlalchemy.exc import OperationalError

        from promptflow._sdk._orm.retry import sqlite_retry

        @sqlite_retry
        def mock_sqlite_op() -> None:
            print("sqlite op...")
            raise OperationalError("statement", "params", "orig")

        # it will finally raise an OperationalError
        with pytest.raises(OperationalError):
            mock_sqlite_op()
        # assert function execution time from stdout
        out, _ = capfd.readouterr()
        assert out.count("sqlite op...") == 3

    def test_resolve_connections_environment_variable_reference(self):
        connections = {
            "test_connection": {
                "type": "AzureOpenAIConnection",
                "value": {
                    "api_key": "${env:AZURE_OPENAI.API_KEY}",
                    "api_base": "${env:AZURE_OPENAI_API_BASE}",
                },
            },
            "test_custom_connection": {
                "type": "CustomConnection",
                "value": {"key": "${env:CUSTOM_KEY}", "key2": "value2"},
            },
        }
        with mock.patch.dict(
            os.environ, {"AZURE_OPENAI.API_KEY": "KEY", "AZURE_OPENAI_API_BASE": "BASE", "CUSTOM_KEY": "CUSTOM_VALUE"}
        ):
            resolve_connections_environment_variable_reference(connections)
        assert connections["test_connection"]["value"]["api_key"] == "KEY"
        assert connections["test_connection"]["value"]["api_base"] == "BASE"
        assert connections["test_custom_connection"]["value"]["key"] == "CUSTOM_VALUE"

    def test_override_connection_config_with_environment_variable(self):
        connections = {
            "test_connection": {
                "type": "AzureOpenAIConnection",
                "value": {
                    "api_key": "KEY",
                    "api_base": "https://gpt-test-eus.openai.azure.com/",
                },
            },
            "test_custom_connection": {
                "type": "CustomConnection",
                "value": {"key": "value1", "key2": "value2"},
            },
        }
        with mock.patch.dict(
            os.environ, {"TEST_CONNECTION_API_BASE": "BASE", "TEST_CUSTOM_CONNECTION_KEY": "CUSTOM_VALUE"}
        ):
            override_connection_config_with_environment_variable(connections)
        assert connections["test_connection"]["value"]["api_key"] == "KEY"
        assert connections["test_connection"]["value"]["api_base"] == "BASE"
        assert connections["test_custom_connection"]["value"]["key"] == "CUSTOM_VALUE"
        assert connections["test_custom_connection"]["value"]["key2"] == "value2"

    def test_generate_flow_tools_json(self) -> None:
        # call twice to ensure system path won't be affected during generation
        for _ in range(2):
            flow_src_path = "./tests/test_configs/flows/flow_with_sys_inject"
            with tempfile.TemporaryDirectory() as temp_dir:
                flow_dst_path = os.path.join(temp_dir, "flow_with_sys_inject")
                shutil.copytree(flow_src_path, flow_dst_path)
                flow_tools_json = generate_flow_tools_json(flow_dst_path, dump=False)
                groundtruth = {
                    "hello.py": {
                        "type": "python",
                        "inputs": {
                            "input1": {
                                "type": [
                                    "string",
                                ],
                            },
                        },
                        "source": "hello.py",
                        "function": "my_python_tool",
                    }
                }
                assert flow_tools_json["code"] == groundtruth

    def test_generate_flow_tools_json_expecting_fail(self) -> None:
        flow_path = "./tests/test_configs/flows/flow_with_invalid_import"
        with pytest.raises(GenerateFlowToolsJsonError) as e:
            generate_flow_tools_json(flow_path, dump=False)
        assert "Generate meta failed, detail error(s):" in str(e.value)
        # raise_error = False
        flow_tools_json = generate_flow_tools_json(flow_path, dump=False, raise_error=False)
        assert len(flow_tools_json["code"]) == 0

    @pytest.mark.parametrize(
        "python_path, env_hash",
        [
            ("D:\\Tools\\Anaconda3\\envs\\pf\\python.exe", ("a9620c3cdb7ccf3ec9f4005e5b19c12d1e1fef80")),
            ("/Users/fake_user/anaconda3/envs/pf/bin/python3.10", ("e3f33eadd9be376014eb75a688930930ca83c056")),
        ],
    )
    def test_generate_connections_dir(self, python_path, env_hash):
        expected_result = (HOME_PROMPT_FLOW_DIR / "envs" / env_hash / "connections").resolve()
        with patch.object(sys, "executable", python_path):
            result = _generate_connections_dir()
            assert result == expected_result

    def test_refresh_connections_dir(self):
        from promptflow._core.tools_manager import collect_package_tools_and_connections

        tools, specs, templates = collect_package_tools_and_connections()

        refresh_connections_dir(specs, templates)
        conn_dir = _generate_connections_dir()
        assert len(os.listdir(conn_dir)) > 0, "No files were generated"

    @pytest.mark.parametrize("concurrent_count", [1, 2, 4, 8])
    def test_concurrent_execution_of_refresh_connections_dir(self, concurrent_count):
        threads = []

        # Create and start threads
        for _ in range(concurrent_count):
            thread = threading.Thread(
                target=lambda: refresh_connections_dir(connection_spec_files=[], connection_template_yamls=[])
            )
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

    @pytest.mark.parametrize(
        "data_path",
        [
            "./tests/test_configs/datas/load_data_cases/colors.csv",
            "./tests/test_configs/datas/load_data_cases/colors.json",
            "./tests/test_configs/datas/load_data_cases/colors.jsonl",
            "./tests/test_configs/datas/load_data_cases/colors.tsv",
            "./tests/test_configs/datas/load_data_cases/colors.parquet",
        ],
    )
    def test_load_data(self, data_path: str) -> None:
        # for csv and tsv format, all columns will be string;
        # for rest, integer will be int and float will be float
        is_string = "csv" in data_path or "tsv" in data_path
        df = load_data(data_path)
        assert len(df) == 3
        assert df[0]["name"] == "Red"
        assert isinstance(df[0]["id_text"], str)
        assert df[0]["id_text"] == "1.0"
        if is_string:
            assert isinstance(df[0]["id_int"], str)
            assert df[0]["id_int"] == "1"
            assert isinstance(df[0]["id_float"], str)
            assert df[0]["id_float"] == "1.0"
        else:
            assert isinstance(df[0]["id_int"], int)
            assert df[0]["id_int"] == 1
            assert isinstance(df[0]["id_float"], float)
            assert df[0]["id_float"] == 1.0

    @pytest.mark.parametrize(
        "data_path",
        [
            "./tests/test_configs/datas/load_data_cases/10k.jsonl",
            "./tests/test_configs/datas/load_data_cases/10k",
        ],
    )
    def test_load_10k_data(self, data_path: str) -> None:
        df = load_data(data_path)
        assert len(df) == 10000
        # specify max_rows_count
        df = load_data(data_path, max_rows_count=5000)
        assert len(df) == 5000


@pytest.mark.unittest
class TestCLIUtils:
    def test_list_of_dict_to_nested_dict(self):
        test_list = [{"node1.connection": "a"}, {"node2.deploy_name": "b"}]
        result = list_of_dict_to_nested_dict(test_list)
        assert result == {"node1": {"connection": "a"}, "node2": {"deploy_name": "b"}}
        test_list = [{"node1.connection": "a"}, {"node1.deploy_name": "b"}]
        result = list_of_dict_to_nested_dict(test_list)
        assert result == {"node1": {"connection": "a", "deploy_name": "b"}}

    def test_append_to_dict_action(self):
        parser = argparse.ArgumentParser(prog="test_dict_action")
        parser.add_argument("--dict", action=AppendToDictAction, nargs="+")
        args = ["--dict", "key1=val1", "'key2=val2'", '"key3=val3"', "key4='val4'", "key5=\"val5'"]
        args = parser.parse_args(args)
        expect_dict = {
            "key1": "val1",
            "key2": "val2",
            "key3": "val3",
            "key4": "val4",
            "key5": "\"val5'",
        }
        assert args.dict[0] == expect_dict

    def test_build_sorted_column_widths_tuple_list(self) -> None:
        columns = ["col1", "col2", "col3"]
        values1 = {"col1": 1, "col2": 4, "col3": 3}
        values2 = {"col1": 3, "col2": 3, "col3": 1}
        margins = {"col1": 1, "col2": 2, "col3": 2}
        # sort by (max(values1, values2) + margins)
        res = _build_sorted_column_widths_tuple_list(columns, values1, values2, margins)
        assert res == [("col2", 6), ("col3", 5), ("col1", 4)]

    def test_calculate_column_widths(self) -> None:
        data = [
            {
                "inputs.url": "https://www.youtube.com/watch?v=o5ZQyXaAv1g",
                "inputs.answer": "Channel",
                "inputs.evidence": "Url",
                "outputs.category": "Channel",
                "outputs.evidence": "URL",
            },
            {
                "inputs.url": "https://arxiv.org/abs/2307.04767",
                "inputs.answer": "Academic",
                "inputs.evidence": "Text content",
                "outputs.category": "Academic",
                "outputs.evidence": "Text content",
            },
            {
                "inputs.url": "https://play.google.com/store/apps/details?id=com.twitter.android",
                "inputs.answer": "App",
                "inputs.evidence": "Both",
                "outputs.category": "App",
                "outputs.evidence": "Both",
            },
        ]
        df = pd.DataFrame(data)
        terminal_width = 120
        res = _calculate_column_widths(df, terminal_width)
        assert res == [4, 23, 13, 15, 15, 15]

# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import datetime
import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import mock
import pandas as pd
import pytest
from _constants import PROMPTFLOW_ROOT
from requests import Response

from promptflow._cli._params import AppendToDictAction
from promptflow._cli._utils import (
    _build_sorted_column_widths_tuple_list,
    _calculate_column_widths,
    list_of_dict_to_nested_dict,
)
from promptflow._constants import LAST_CHECK_TIME, PF_VERSION_CHECK
from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR, PROMPT_FLOW_HOME_DIR_ENV_VAR
from promptflow._sdk._errors import GenerateFlowToolsJsonError
from promptflow._sdk._telemetry.logging_handler import get_scrubbed_cloud_role
from promptflow._sdk._utilities.general_utils import (
    _generate_connections_dir,
    decrypt_secret_value,
    encrypt_secret_value,
    gen_uuid_by_compute_info,
    generate_flow_tools_json,
    get_mac_address,
    get_system_info,
    refresh_connections_dir,
    resolve_flow_language,
    resolve_flow_path,
)
from promptflow._sdk._version_hint_utils import check_latest_version
from promptflow._utils.load_data import load_data
from promptflow._utils.retry_utils import http_retry_wrapper, retry
from promptflow._utils.utils import snake_to_camel
from promptflow.core._utils import (
    override_connection_config_with_environment_variable,
    resolve_connections_environment_variable_reference,
)
from promptflow.exceptions import UserErrorException

TEST_ROOT = PROMPTFLOW_ROOT / "tests"
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
        assert out.count("sqlite op...") <= 10

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

        # test bad cases
        connections = {
            "test_connection": {
                "type": "AzureOpenAIConnection",
                "value": {"none_value": None, "integer_value": 1, "float_value": 1.0, "dict_value": {}},
            },
        }
        resolve_connections_environment_variable_reference(connections)
        assert connections["test_connection"]["value"] == {
            "none_value": None,
            "integer_value": 1,
            "float_value": 1.0,
            "dict_value": {},
        }

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

    def test_concurrent_hint_for_update(self):
        def mock_check_latest_version():
            time.sleep(5)
            check_latest_version()

        with patch("promptflow._sdk._version_hint_utils.datetime") as mock_datetime, patch(
            "promptflow._sdk._version_hint_utils.check_latest_version", side_effect=mock_check_latest_version
        ):
            from promptflow._sdk._telemetry import monitor_operation

            class HintForUpdate:
                @monitor_operation(activity_name="pf.flows.test")
                def hint_func(self):
                    return

            current_time = datetime.datetime.now()
            mock_datetime.datetime.now.return_value = current_time
            mock_datetime.datetime.strptime.return_value = current_time - datetime.timedelta(days=8)
            mock_datetime.timedelta.return_value = datetime.timedelta(days=7)
            HintForUpdate().hint_func()
            assert Path(HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK).exists()
            with open(HOME_PROMPT_FLOW_DIR / PF_VERSION_CHECK, "r") as f:
                cached_versions = json.load(f)
            # since mock_check_latest_version is a demon thread, it will exit when main thread complete, so
            # LAST_CHECK_TIME won't be updated since sleep 5s
            assert LAST_CHECK_TIME not in cached_versions or cached_versions[LAST_CHECK_TIME] != str(current_time)

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
        max_rows_count = 5000
        head_rows = load_data(data_path, max_rows_count=max_rows_count)
        assert len(head_rows) == max_rows_count
        assert head_rows == df[:max_rows_count]

    @pytest.mark.parametrize(
        "script_name, expected_result",
        [
            ("pfs", "pfs"),
            ("pfutil.py", "pfutil.py"),
            ("pf", "pf"),
            ("pfazure", "pfazure"),
            ("pf.exe", "pf.exe"),
            ("pfazure.exe", "pfazure.exe"),
            ("app.py", "app.py"),
            ("python -m unittest", "python -m unittest"),
            ("pytest", "pytest"),
            ("gunicorn", "gunicorn"),
            ("ipykernel_launcher.py", "ipykernel_launcher.py"),
            ("jupyter-notebook", "jupyter-notebook"),
            ("jupyter-lab", "jupyter-lab"),
            ("python", "python"),
            ("Unknown Application", "Unknown Application"),
            ("unknown_script.py", "***.py"),
            ("path/to/unknown_script.py", "***.py"),
            (r"path\to\unknown_script.py", "***.py"),
            ('invalid_chars_\\/:*?"<>|', "***"),
        ],
    )
    def test_get_scrubbed_cloud_role(self, script_name, expected_result):
        with mock.patch("sys.argv", [script_name]):
            assert get_scrubbed_cloud_role() == expected_result

    def test_configure_pf_home_dir(self, tmpdir) -> None:
        from promptflow._sdk import _constants

        custom_pf_home_dir_path = Path(tmpdir / ".promptflow").resolve()
        assert not custom_pf_home_dir_path.exists()
        with patch.dict(os.environ, {PROMPT_FLOW_HOME_DIR_ENV_VAR: custom_pf_home_dir_path.as_posix()}):
            importlib.reload(_constants)
            assert _constants.HOME_PROMPT_FLOW_DIR.as_posix() == custom_pf_home_dir_path.as_posix()
            assert _constants.HOME_PROMPT_FLOW_DIR.is_dir()
        importlib.reload(_constants)

    def test_configure_pf_home_dir_with_invalid_path(self) -> None:
        from promptflow._sdk import _constants

        invalid_path = "/invalid:path"
        with patch.dict(os.environ, {PROMPT_FLOW_HOME_DIR_ENV_VAR: invalid_path}):
            assert os.getenv(PROMPT_FLOW_HOME_DIR_ENV_VAR) == invalid_path
            importlib.reload(_constants)
            assert _constants.HOME_PROMPT_FLOW_DIR.as_posix() == (Path.home() / ".promptflow").resolve().as_posix()
        importlib.reload(_constants)

    def test_resolve_flow_path_allow_prompty_dir(self):
        flow_dir, flow_file_name = resolve_flow_path(
            "./tests/test_configs/prompty/single_prompty", allow_prompty_dir=True
        )
        assert flow_file_name == "prompty_example.prompty"

        flow_dir, flow_file_name = resolve_flow_path(
            "./tests/test_configs/prompty", allow_prompty_dir=True, check_flow_exist=False
        )
        assert flow_file_name == "flow.dag.yaml"

        with pytest.raises(UserErrorException) as ex:
            resolve_flow_path("./tests/test_configs/prompty", allow_prompty_dir=True)
        assert "neither flow.dag.yaml nor flow.flex.yaml" in ex.value.message

        with pytest.raises(UserErrorException) as ex:
            resolve_flow_path("./tests/test_configs/prompty/single_prompty")
        assert "neither flow.dag.yaml nor flow.flex.yaml" in ex.value.message

    def test_resolve_flow_language(self):
        # dag flow
        lan = resolve_flow_language(flow_path=TEST_ROOT / "test_configs" / "flows" / "csharp_flow")
        assert lan == "csharp"

        lan = resolve_flow_language(flow_path=TEST_ROOT / "test_configs" / "flows" / "chat_flow")
        assert lan == "python"

        # flex flow
        lan = resolve_flow_language(flow_path=TEST_ROOT / "test_configs" / "eager_flows" / "basic_callable_class")
        assert lan == "python"

        lan = resolve_flow_language(
            flow_path=TEST_ROOT / "test_configs" / "eager_flows" / "basic_dummy_csharp_flex_flow"
        )
        assert lan == "csharp"

        # prompty
        lan = resolve_flow_language(flow_path=TEST_ROOT / "test_configs" / "prompty" / "prompty_example.prompty")
        assert lan == "python"

        with pytest.raises(UserErrorException) as ex:
            resolve_flow_language()
        assert "Either flow_path or yaml_dict should be provided." in ex.value.message

        with pytest.raises(UserErrorException) as ex:
            resolve_flow_language()
        assert "Either flow_path or yaml_dict should be provided." in ex.value.message

        with pytest.raises(UserErrorException) as ex:
            resolve_flow_language(flow_path="mock_path", yaml_dict="mock_dict")
        assert "Only one of flow_path and yaml_dict should be provided." in ex.value.message

        with pytest.raises(UserErrorException) as ex:
            resolve_flow_language(
                flow_path=TEST_ROOT
                / "test_configs"
                / "eager_flows"
                / "basic_callable_class"
                / "simple_callable_class.py"
            )
        assert "suffix must be yaml, yml or prompty" in ex.value.message

        with pytest.raises(UserErrorException) as ex:
            resolve_flow_language(flow_path="mock_path")
        assert "mock_path does not exist." in ex.value.message


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

    def test_calculate_column_widths_edge_case(self) -> None:
        nan = float("nan")
        # test case comes from examples/flow/evaluation/eval-qna-non-rag
        data = [
            {
                "inputs.groundtruth": "The Alpine Explorer Tent has the highest rainfly waterproof rating at 3000m",
                "inputs.answer": "There are various tents available in the market that offer different levels of waterproofing. However, one tent that is often highly regarded for its waterproofing capabilities is the MSR Hubba Hubba NX tent. It features a durable rainfly and a bathtub-style floor construction, both of which contribute to its excellent water resistance. It is always recommended to read product specifications and customer reviews to ensure you find a tent that meets your specific waterproofing requirements.",  # noqa: E501
                "inputs.context": "{${data.context}}",
                "inputs.question": "Which tent is the most waterproof?",
                "inputs.metrics": "gpt_groundedness,f1_score",
                "inputs.line_number": 0,
                "inputs.ground_truth": "The Alpine Explorer Tent has the highest rainfly waterproof rating at 3000m",
                "outputs.line_number": 0,
                "outputs.ada_similarity": nan,
                "outputs.f1_score": 0.049999999999999996,
                "outputs.gpt_coherence": nan,
                "outputs.gpt_fluency": nan,
                "outputs.gpt_groundedness": 3.0,
                "outputs.gpt_relevance": nan,
                "outputs.gpt_similarity": nan,
            },
            {
                "inputs.groundtruth": "The Adventure Dining Table has a higher weight capacity than all of the other camping tables mentioned",  # noqa: E501
                "inputs.answer": "There are various camping tables available that can hold different amounts of weight. Some heavy-duty camping tables can hold up to 300 pounds or more, while others may have lower weight capacities. It's important to check the specifications of each table before purchasing to ensure it can support the weight you require.",  # noqa: E501
                "inputs.context": "{${data.context}}",
                "inputs.question": "Which tent is the most waterproof?",
                "inputs.metrics": "gpt_groundedness,f1_score",
                "inputs.ground_truth": "The Alpine Explorer Tent has the highest rainfly waterproof rating at 3000m",
                "outputs.line_number": 1,
                "outputs.ada_similarity": nan,
                "outputs.f1_score": 0.0,
                "outputs.gpt_coherence": nan,
                "outputs.gpt_fluency": nan,
                "outputs.gpt_groundedness": 3.0,
                "outputs.gpt_relevance": nan,
                "outputs.gpt_similarity": nan,
            },
        ]
        df = pd.DataFrame(data)
        terminal_width = 74  # GitHub Actions scenario
        res = _calculate_column_widths(df, terminal_width)
        # the column width should at least 1 to avoid tabulate error
        assert res == [4, 1, 13, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]


@pytest.mark.unittest
class TestRetryUtils:
    def test_retry(self):
        counter = 0

        class A:
            def mock_f(self):
                return 1

        class B(A):
            @retry(Exception, tries=2, delay=1, backoff=1)
            def mock_f(self):
                nonlocal counter
                counter += 1
                raise Exception("mock exception")

        with pytest.raises(Exception):
            B().mock_f()
        assert counter == 2

    def test_http_retry(self):
        counter = 0

        def mock_http_request():
            nonlocal counter
            counter += 1
            resp = Response()
            resp.status_code = 429
            return resp

        http_retry_wrapper(mock_http_request, tries=2, delay=1, backoff=1)()
        assert counter == 2

    def test_gen_uuid_by_compute_info(self):
        uuid1 = gen_uuid_by_compute_info()
        uuid2 = gen_uuid_by_compute_info()
        assert uuid1 == uuid2

        mac_address = get_mac_address()
        assert mac_address

        host_name, system, machine = get_system_info()
        system_info_hash = hashlib.sha256((host_name + system + machine).encode()).hexdigest()
        compute_info_hash = hashlib.sha256((mac_address + system_info_hash).encode()).hexdigest()
        assert str(uuid.uuid5(uuid.NAMESPACE_OID, compute_info_hash)) == gen_uuid_by_compute_info()

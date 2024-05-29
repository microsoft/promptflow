import filecmp
import importlib
import importlib.util
import json
import logging
import os
import os.path
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from tempfile import mkdtemp
from time import sleep
from typing import Dict, List
from unittest.mock import patch

import mock
import pytest
from _constants import PROMPTFLOW_ROOT
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from promptflow._cli._pf.entry import main
from promptflow._constants import FLOW_FLEX_YAML, LINE_NUMBER_KEY, PF_USER_AGENT
from promptflow._core.metric_logger import add_metric_logger
from promptflow._sdk._constants import LOGGER_NAME, SCRUBBED_VALUE, ExperimentStatus
from promptflow._sdk._errors import RunNotFoundError
from promptflow._sdk.operations._local_storage_operations import LocalStorageOperations
from promptflow._sdk.operations._run_operations import RunOperations
from promptflow._utils.context_utils import _change_working_dir, inject_sys_path
from promptflow._utils.user_agent_utils import ClientUserAgentUtil, setup_user_agent_to_operation_context
from promptflow._utils.utils import environment_variable_overwrite, parse_ua_to_dict
from promptflow._utils.yaml_utils import dump_yaml, load_yaml
from promptflow.tracing._operation_context import OperationContext

FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/flows"
EAGER_FLOWS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/eager_flows"
EXPERIMENT_DIR = PROMPTFLOW_ROOT / "tests/test_configs/experiments"
RUNS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/runs"
CONNECTIONS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/connections"
DATAS_DIR = PROMPTFLOW_ROOT / "tests/test_configs/datas"
TOOL_ROOT = PROMPTFLOW_ROOT / "tests/test_configs/tools"
PROMPTY_DIR = PROMPTFLOW_ROOT / "tests/test_configs/prompty"

TARGET_URL = "https://www.youtube.com/watch?v=o5ZQyXaAv1g"


# TODO: move this to a shared utility module
def run_pf_command(*args, cwd=None):
    """Run a pf command with the given arguments and working directory.

    There have been some unknown issues in using subprocess on CI, so we use this function instead, which will also
    provide better debugging experience.
    """
    origin_argv, origin_cwd = sys.argv, os.path.abspath(os.curdir)
    try:
        sys.argv = ["pf"] + list(args)
        if cwd:
            os.chdir(cwd)
        main()
    finally:
        sys.argv = origin_argv
        os.chdir(origin_cwd)


def compare_directories(dir1, dir2, ingore_path_name):
    dir1 = Path(dir1)
    dir2 = Path(dir2)
    dir1_content = [item for item in dir1.iterdir() if item.name not in ingore_path_name]
    dir2_content = [item for item in dir2.iterdir() if item.name not in ingore_path_name]

    if len(dir1_content) != len(dir2_content):
        raise Exception(f"These two folders {dir1_content} and {dir2_content} are different.")

    for path1 in dir1_content:
        path2 = dir2 / path1.name
        if not path2.exists():
            raise Exception(f"The path {path2} does not exist.")
        if path1.is_file() and path2.is_file():
            if not filecmp.cmp(path1, path2):
                raise Exception(f"These two files {path1} and {path2} are different.")
        elif path1.is_dir() and path2.is_dir():
            compare_directories(path1, path2, ingore_path_name)
        else:
            raise Exception(f"These two path {path1} and {path2} are different.")


@pytest.mark.usefixtures(
    "use_secrets_config_file", "recording_injection", "setup_local_connection", "install_custom_tool_pkg"
)
@pytest.mark.cli_test
@pytest.mark.e2etest
class TestCli:
    def test_pf_version(self, capfd):
        import re

        from pkg_resources import parse_version

        run_pf_command("--version")
        out, err = capfd.readouterr()

        pf_versions = re.findall(r'"\S+":\s+"(\S+)"', out)
        for pf_version in pf_versions:
            assert parse_version(pf_version)

    def test_basic_flow_run(self, capfd) -> None:
        # fetch std out
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--data",
            f"{DATAS_DIR}/webClassification3.jsonl",
            "--name",
            str(uuid.uuid4()),
        )
        out, _ = capfd.readouterr()
        assert "Completed" in out

    def test_basic_flow_run_batch_and_eval(self, capfd) -> None:
        run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--data",
            f"{DATAS_DIR}/webClassification3.jsonl",
            "--name",
            run_id,
        )
        out, _ = capfd.readouterr()
        assert "Completed" in out

        # Check the CLI works correctly when the parameter is surrounded by quotation, as below shown:
        # --param "key=value" key="value"
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/classification_accuracy_evaluation",
            "--column-mapping",
            "'groundtruth=${data.answer}'",
            "prediction='${run.outputs.category}'",
            "variant_id=${data.variant_id}",
            "--data",
            f"{DATAS_DIR}/webClassification3.jsonl",
            "--run",
            run_id,
        )
        out, _ = capfd.readouterr()
        assert "Completed" in out

    def test_submit_run_with_yaml(self, capfd):
        run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--file",
            "./sample_bulk_run.yaml",
            "--name",
            run_id,
            cwd=f"{RUNS_DIR}",
        )
        out, _ = capfd.readouterr()
        assert "Completed" in out

        run_pf_command(
            "run",
            "create",
            "--file",
            "./sample_eval_run.yaml",
            "--run",
            run_id,
            cwd=f"{RUNS_DIR}",
        )
        out, _ = capfd.readouterr()
        assert "Completed" in out

    def test_submit_batch_variant(self, local_client):
        run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--data",
            f"{DATAS_DIR}/webClassification3.jsonl",
            "--name",
            run_id,
            "--variant",
            "${summarize_text_content.variant_0}",
        )
        run = local_client.runs.get(name=run_id)
        local_storage = LocalStorageOperations(run)
        detail = local_storage.load_detail()
        tuning_node = next((x for x in detail["node_runs"] if x["node"] == "summarize_text_content"), None)
        # used variant_0 config, defaults using variant_1
        assert tuning_node["inputs"]["temperature"] == 0.2

    def test_environment_variable_overwrite(self, local_client, local_aoai_connection):
        run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--name",
            run_id,
            "--flow",
            f"{FLOWS_DIR}/print_env_var",
            "--data",
            f"{DATAS_DIR}/env_var_names.jsonl",
            "--environment-variables",
            "API_BASE=${azure_open_ai_connection.api_base}",
        )
        outputs = local_client.runs._get_outputs(run=run_id)
        assert outputs["output"][0] == local_aoai_connection.api_base

    def test_connection_overwrite(self, local_alt_aoai_connection, capfd):
        # CLi command will fail with SystemExit
        with pytest.raises(SystemExit):
            run_pf_command(
                "run",
                "create",
                "--flow",
                f"{FLOWS_DIR}/web_classification",
                "--data",
                f"{DATAS_DIR}/webClassification3.jsonl",
                "--connection",
                "classify_with_llm.connection=not_exist",
            )

        out, _ = capfd.readouterr()
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--data",
            f"{DATAS_DIR}/webClassification3.jsonl",
            "--connection",
            "classify_with_llm.connection=new_ai_connection",
        )
        out, _ = capfd.readouterr()
        assert "Completed" in out

        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--data",
            f"{DATAS_DIR}/webClassification3.jsonl",
            "--connection",
            "classify_with_llm.model=new_model",
        )
        out, _ = capfd.readouterr()
        assert "Completed" in out

    def test_create_with_set(self, local_client):
        run_id = str(uuid.uuid4())
        display_name = "test_run"
        description = "test description"
        run_pf_command(
            "run",
            "create",
            "--name",
            run_id,
            "--flow",
            f"{FLOWS_DIR}/print_env_var",
            "--data",
            f"{DATAS_DIR}/env_var_names.jsonl",
            "--environment-variables",
            "API_BASE=${azure_open_ai_connection.api_base}",
            "--set",
            f"display_name={display_name}",
            "tags.key=val",
            f"description={description}",
        )
        run = local_client.runs.get(run_id)
        assert display_name in run.display_name
        assert run.tags == {"key": "val"}
        assert run.description == description

        run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--file",
            "./sample_bulk_run.yaml",
            "--name",
            run_id,
            "--set",
            f"display_name={display_name}",
            "tags.key=val",
            f"description={description}",
            cwd=f"{RUNS_DIR}",
        )
        assert display_name in run.display_name
        assert run.tags == {"key": "val"}
        assert run.description == description

    def test_pf_flow_test(self):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--inputs",
            "url=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
            "answer=Channel",
            "evidence=Url",
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / "flow.output.json"
        assert output_path.exists()
        log_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / "flow.log"
        with open(log_path, "r") as f:
            previous_log_content = f.read()

        # Test without input
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / "flow.output.json"
        assert output_path.exists()
        log_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / "flow.log"
        with open(log_path, "r") as f:
            log_content = f.read()
        assert previous_log_content not in log_content

        # Test flow test with simple input file
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--inputs",
            f"{DATAS_DIR}/webClassification1.jsonl",
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / "flow.output.json"
        assert output_path.exists()

        # Test flow test with simple input file
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--inputs",
            f"{DATAS_DIR}/webClassification.json",
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / "flow.output.json"
        assert output_path.exists()

        # Test flow test with invalid simple input file
        with pytest.raises(ValueError) as ex:
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/web_classification",
                "--inputs",
                f"{DATAS_DIR}/invalid_path.json",
            )
        assert "Cannot find inputs file" in ex.value.args[0]

        # Test flow test with invalid file extension
        with pytest.raises(ValueError) as ex:
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/web_classification",
                "--inputs",
                f"{DATAS_DIR}/logo.jpg",
            )
        assert "Only support jsonl or json file as input" in ex.value.args[0]

    def test_flow_with_aad_connection(self):
        run_pf_command("flow", "test", "--flow", f"{FLOWS_DIR}/flow_with_aad_connection")
        output_path = Path(FLOWS_DIR) / "flow_with_aad_connection" / ".promptflow" / "flow.output.json"
        assert output_path.exists()
        output = json.loads(open(output_path, "r", encoding="utf-8").read())
        assert output["result"] == "meid_token"

    def test_pf_flow_test_with_non_english_input_output(self, capsys):
        # disable trace to not invoke prompt flow service, which will print unexpected content to stdout
        with mock.patch("promptflow._sdk._tracing.is_trace_feature_disabled", return_value=True):
            question = "什么是 chat gpt"
            run_pf_command("flow", "test", "--flow", f"{FLOWS_DIR}/chat_flow", "--inputs", f'question="{question}"')
            stdout, _ = capsys.readouterr()
            output_path = Path(FLOWS_DIR) / "chat_flow" / ".promptflow" / "flow.output.json"
            assert output_path.exists()
            with open(output_path, "r", encoding="utf-8") as f:
                outputs = json.load(f)
                assert outputs["answer"] in json.loads(stdout)["answer"]

            detail_path = Path(FLOWS_DIR) / "chat_flow" / ".promptflow" / "flow.detail.json"
            assert detail_path.exists()
            with open(detail_path, "r", encoding="utf-8") as f:
                detail = json.load(f)
                assert detail["flow_runs"][0]["inputs"]["question"] == question
                assert detail["flow_runs"][0]["output"]["answer"] == outputs["answer"]

    def test_pf_flow_with_variant(self, capsys):
        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copytree((Path(FLOWS_DIR) / "web_classification").resolve().as_posix(), temp_dir, dirs_exist_ok=True)

            dag = Path(temp_dir) / "flow.dag.yaml"
            flow_dict = load_yaml(dag)

            node_name = "summarize_text_content"
            node = next(filter(lambda item: item["name"] == node_name, flow_dict["nodes"]))
            flow_dict["nodes"].remove(node)
            flow_dict["nodes"].append({"name": node_name, "use_variants": True})
            with open(Path(temp_dir) / "flow.dag.yaml", "w") as f:
                dump_yaml(flow_dict, f)

            run_pf_command(
                "flow",
                "test",
                "--flow",
                temp_dir,
                "--inputs",
                "url=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
                "answer=Channel",
                "evidence=Url",
            )
            output_path = Path(temp_dir) / ".promptflow" / "flow.output.json"
            assert output_path.exists()

            run_pf_command(
                "flow",
                "test",
                "--flow",
                temp_dir,
                "--inputs",
                "url=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
                "answer=Channel",
                "evidence=Url",
                "--variant",
                "'${summarize_text_content.variant_1}'",
            )
            output_path = Path(temp_dir) / ".promptflow" / "flow-summarize_text_content-variant_1.output.json"
            assert output_path.exists()

            # Test flow dag with invalid format
            node_name = flow_dict["nodes"][0]["name"]
            flow_dict["nodes"][0]["use_variants"] = True
            flow_dict["node_variants"][node_name] = {
                "default_variant_id": "invalid_variant",
                "variants": [{"variant_0": {}}],
            }
            with open(Path(temp_dir) / "flow.dag.yaml", "w") as f:
                dump_yaml(flow_dict, f)
            with pytest.raises(SystemExit):
                run_pf_command(
                    "flow",
                    "test",
                    "--flow",
                    temp_dir,
                    "--inputs",
                    "url=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
                    "answer=Channel",
                    "evidence=Url",
                    "--variant",
                    "${summarize_text_content.variant_1}",
                )
            outerr = capsys.readouterr()
            assert f"Cannot find the variant invalid_variant for {node_name}." in outerr.out

    def test_pf_flow_test_single_node(self):
        node_name = "fetch_text_content_from_url"
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--inputs",
            "inputs.url="
            "https://www.microsoft.com/en-us/d/xbox-wireless-controller-stellar-shift-special-edition/94fbjc7h0h6h",
            "--node",
            node_name,
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / f"flow-{node_name}.node.detail.json"
        assert output_path.exists()

        node_name = "fetch_text_content_from_url"
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--inputs",
            "url="
            "https://www.microsoft.com/en-us/d/xbox-wireless-controller-stellar-shift-special-edition/94fbjc7h0h6h",
            "--node",
            node_name,
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / f"flow-{node_name}.node.detail.json"
        assert output_path.exists()

        # Test node with node reference input
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--inputs",
            'input_str={"category": "App", "evidence": "URL"}',
            "--node",
            "convert_to_dict",
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / "flow-convert_to_dict.node.detail.json"
        assert output_path.exists()

        # Test without input
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--node",
            node_name,
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / f"flow-{node_name}.node.detail.json"
        assert output_path.exists()

        # Test with input file
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--node",
            node_name,
            "--input",
            f"{FLOWS_DIR}/web_classification/{node_name}_input.jsonl",
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / f"flow-{node_name}.node.detail.json"
        assert output_path.exists()

        # Test with input file
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--node",
            node_name,
            "--inputs",
            f"{FLOWS_DIR}/web_classification/{node_name}_input.jsonl",
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / f"flow-{node_name}.node.detail.json"
        assert output_path.exists()

    def test_pf_flow_test_debug_single_node(self):
        node_name = "fetch_text_content_from_url"
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--inputs",
            "inputs.url="
            "https://www.microsoft.com/en-us/d/xbox-wireless-controller-stellar-shift-special-edition/94fbjc7h0h6h",
            "--node",
            node_name,
            "--debug",
        )

        # Debug node with node reference input
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--inputs",
            'classify_with_llm.output={"category": "App", "evidence": "URL"}',
            "--node",
            "convert_to_dict",
            "--debug",
        )

    def test_pf_flow_test_with_additional_includes(self):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification_with_additional_include",
            "--inputs",
            "url=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
            "answer=Channel",
            "evidence=Url",
        )
        output_path = (
            Path(FLOWS_DIR) / "web_classification_with_additional_include" / ".promptflow" / "flow.output.json"
        )
        assert output_path.exists()

        node_name = "fetch_text_content_from_url"
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification_with_additional_include",
            "--inputs",
            "inputs.url="
            "https://www.microsoft.com/en-us/d/xbox-wireless-controller-stellar-shift-special-edition/94fbjc7h0h6h",
            "--node",
            node_name,
        )

    def test_pf_flow_test_with_symbolic(self, prepare_symbolic_flow):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification_with_symbolic",
            "--inputs",
            "url=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
            "answer=Channel",
            "evidence=Url",
        )
        output_path = Path(FLOWS_DIR) / "web_classification_with_symbolic" / ".promptflow" / "flow.output.json"
        assert output_path.exists()

        node_name = "fetch_text_content_from_url"
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification_with_symbolic",
            "--inputs",
            "inputs.url="
            "https://www.microsoft.com/en-us/d/xbox-wireless-controller-stellar-shift-special-edition/94fbjc7h0h6h",
            "--node",
            node_name,
        )

    @pytest.mark.parametrize(
        "flow_folder_name, env_key, except_value",
        [
            pytest.param(
                "print_env_var",
                "API_BASE",
                "${azure_open_ai_connection.api_base}",
                id="TestFlowWithEnvironmentVariables",
            ),
            pytest.param(
                "flow_with_environment_variables",
                "env1",
                "2",
                id="LoadEnvVariablesWithoutOverridesInYaml",
            ),
        ],
    )
    def test_flow_test_with_environment_variable(self, flow_folder_name, env_key, except_value, local_client):
        from promptflow._sdk._orchestrator.utils import SubmitterHelper

        def validate_stdout(detail_path):
            with open(detail_path, "r") as f:
                details = json.load(f)
                assert details["node_runs"][0]["logs"]["stdout"]

        env = {env_key: except_value}
        SubmitterHelper.resolve_environment_variables(env, local_client)
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/{flow_folder_name}",
            "--inputs",
            f"key={env_key}",
            "--environment-variables",
            "API_BASE=${azure_open_ai_connection.api_base}",
        )
        with open(Path(FLOWS_DIR) / flow_folder_name / ".promptflow" / "flow.output.json", "r") as f:
            outputs = json.load(f)
        assert outputs["output"] == env[env_key]
        validate_stdout(Path(FLOWS_DIR) / flow_folder_name / ".promptflow" / "flow.detail.json")

        # Test log contains user printed outputs
        log_path = Path(FLOWS_DIR) / flow_folder_name / ".promptflow" / "flow.log"
        with open(log_path, "r") as f:
            log_content = f.read()
        assert env[env_key] in log_content

        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/{flow_folder_name}",
            "--inputs",
            f"inputs.key={env_key}",
            "--environment-variables",
            "API_BASE=${azure_open_ai_connection.api_base}",
            "--node",
            "print_env",
        )
        with open(Path(FLOWS_DIR) / flow_folder_name / ".promptflow" / "flow-print_env.node.output.json", "r") as f:
            outputs = json.load(f)
        assert outputs["value"] == env[env_key]
        validate_stdout(Path(FLOWS_DIR) / flow_folder_name / ".promptflow" / "flow-print_env.node.detail.json")

    def _validate_requirement(self, flow_path):
        with open(flow_path) as f:
            flow_dict = load_yaml(f)
        assert flow_dict.get("environment", {}).get("python_requirements_txt", None)
        assert (flow_path.parent / flow_dict["environment"]["python_requirements_txt"]).exists()

    def test_flow_with_exception(self, capsys):
        with pytest.raises(SystemExit):
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/web_classification_with_exception",
            )
        captured = capsys.readouterr()
        assert "Execution failure in 'convert_to_dict': (Exception) mock exception" in captured.out
        output_path = Path(FLOWS_DIR) / "web_classification_with_exception" / ".promptflow" / "flow.detail.json"
        assert output_path.exists()

        with pytest.raises(SystemExit):
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/web_classification_with_exception",
                "--inputs",
                'classify_with_llm.output={"category": "App", "evidence": "URL"}',
                "--node",
                "convert_to_dict",
            )
        captured = capsys.readouterr()
        assert "convert_to_dict.py" in captured.out
        assert "mock exception" in captured.out
        output_path = (
            Path(FLOWS_DIR)
            / "web_classification_with_exception"
            / ".promptflow"
            / "flow-convert_to_dict.node.detail.json"
        )
        assert output_path.exists()

    def test_init_eval_flow(self):
        temp_dir = mkdtemp()
        with _change_working_dir(temp_dir):
            flow_name = "eval_flow"
            # Init standard flow
            run_pf_command(
                "flow",
                "init",
                "--flow",
                flow_name,
                "--type",
                "evaluation",
            )
            ignore_file_path = Path(temp_dir) / flow_name / ".gitignore"
            assert ignore_file_path.exists()
            ignore_file_path.unlink()
            # TODO remove variant_id & line_number in evaluate template
            run_pf_command("flow", "test", "--flow", flow_name, "--inputs", "groundtruth=App", "prediction=App")
            self._validate_requirement(Path(temp_dir) / flow_name / "flow.dag.yaml")

    def test_init_chat_flow(self):
        temp_dir = mkdtemp()
        with _change_working_dir(temp_dir):
            flow_name = "chat_flow"
            # Init standard flow
            run_pf_command(
                "flow",
                "init",
                "--flow",
                flow_name,
                "--type",
                "chat",
            )
            ignore_file_path = Path(temp_dir) / flow_name / ".gitignore"
            assert ignore_file_path.exists()
            ignore_file_path.unlink()

            # Only azure openai connection in test env
            with open(Path(temp_dir) / flow_name / "flow.dag.yaml", "r") as f:
                flow_dict = load_yaml(f)
            flow_dict["nodes"][0]["provider"] = "AzureOpenAI"
            flow_dict["nodes"][0]["connection"] = "azure_open_ai_connection"
            with open(Path(temp_dir) / flow_name / "flow.dag.yaml", "w") as f:
                dump_yaml(flow_dict, f)

            run_pf_command("flow", "test", "--flow", flow_name, "--inputs", "question=hi")
            self._validate_requirement(Path(temp_dir) / flow_name / "flow.dag.yaml")

    def test_flow_init(self, capsys):
        temp_dir = mkdtemp()
        with _change_working_dir(temp_dir):
            flow_name = "standard_flow"
            # Init standard flow
            run_pf_command(
                "flow",
                "init",
                "--flow",
                flow_name,
                "--type",
                "standard",
            )
            self._validate_requirement(Path(temp_dir) / flow_name / "flow.dag.yaml")
            ignore_file_path = Path(temp_dir) / flow_name / ".gitignore"
            requirements_file_path = Path(temp_dir) / flow_name / "requirements.txt"
            assert ignore_file_path.exists()
            assert requirements_file_path.exists()
            ignore_file_path.unlink()
            run_pf_command("flow", "test", "--flow", flow_name, "--inputs", "text=value")

            jinja_name = "input1"
            run_pf_command(
                "flow",
                "init",
                "--flow",
                flow_name,
                "--entry",
                "hello.py",
                "--function",
                "my_python_tool",
                "--prompt-template",
                f"{jinja_name}=hello.jinja2",
            )
            self._validate_requirement(Path(temp_dir) / flow_name / "flow.dag.yaml")
            assert ignore_file_path.exists()
            assert requirements_file_path.exists()
            with open(Path(temp_dir) / flow_name / ".promptflow" / "flow.tools.json", "r") as f:
                tools_dict = json.load(f)["code"]
                assert jinja_name in tools_dict
                assert len(tools_dict[jinja_name]["inputs"]) == 1
                assert tools_dict[jinja_name]["inputs"]["text"]["type"] == ["string"]
                assert tools_dict[jinja_name]["source"] == "hello.jinja2"

            # Test prompt-template doesn't exist
            run_pf_command(
                "flow",
                "init",
                "--flow",
                flow_name,
                "--entry",
                "hello.py",
                "--function",
                "my_python_tool",
                "--prompt-template",
                f"{jinja_name}={jinja_name}.jinja2",
            )
            self._validate_requirement(Path(temp_dir) / flow_name / "flow.dag.yaml")
            assert (Path(temp_dir) / flow_name / f"{jinja_name}.jinja2").exists()

            # Test template name doesn't exist in python function
            jinja_name = "mock_jinja"
            with pytest.raises(SystemExit):
                run_pf_command(
                    "flow",
                    "init",
                    "--flow",
                    flow_name,
                    "--entry",
                    "hello.py",
                    "--function",
                    "my_python_tool",
                    "--prompt-template",
                    f"{jinja_name}={jinja_name}.jinja2",
                )
                _, err = capsys.readouterr()
                assert f"Template parameter {jinja_name} doesn't find in python function arguments." in err

            with pytest.raises(SystemExit):
                run_pf_command("flow", "init")
            _, err = capsys.readouterr()
            assert "pf flow init: error: the following arguments are required: --flow" in err

    def test_flow_init_intent_copilot(self):
        flow_path = os.path.join(FLOWS_DIR, "intent-copilot")
        run_pf_command(
            "flow",
            "init",
            "--flow",
            flow_path,
            "--entry",
            "intent.py",
            "--function",
            "extract_intent",
            "--prompt-template",
            "chat_prompt=user_intent_zero_shot.jinja2",
        )
        with open(Path(flow_path) / "flow.dag.yaml", "r") as f:
            flow_dict = load_yaml(f)
            assert "chat_history" in flow_dict["inputs"]
            assert "customer_info" in flow_dict["inputs"]
            chat_prompt_node = next(filter(lambda item: item["name"] == "chat_prompt", flow_dict["nodes"]))
            assert "chat_history" in chat_prompt_node["inputs"]
            assert "customer_info" in chat_prompt_node["inputs"]

    def test_flow_init_with_connection_and_deployment(self):
        def check_connection_and_deployment(flow_folder, connection, deployment):
            with open(Path(flow_folder) / "flow.dag.yaml", "r") as f:
                flow_dict = load_yaml(f)
                assert flow_dict["nodes"][0]["inputs"]["deployment_name"] == deployment
                assert flow_dict["nodes"][0]["connection"] == connection

        temp_dir = mkdtemp()
        with _change_working_dir(temp_dir):
            flow_name = "chat_flow"
            flow_folder = Path(temp_dir) / flow_name
            # When configure local connection provider, init chat flow without connection and deployment.
            run_pf_command(
                "flow",
                "init",
                "--flow",
                flow_name,
                "--type",
                "chat",
            )
            # Assert connection files created
            assert (flow_folder / "azure_openai.yaml").exists()
            assert (flow_folder / "openai.yaml").exists()

            # When configure local connection provider, init chat flow with connection and deployment.
            connection = "connection_name"
            deployment = "deployment_name"
            run_pf_command(
                "flow",
                "init",
                "--flow",
                flow_name,
                "--type",
                "chat",
                "--connection",
                connection,
                "--deployment",
                deployment,
                "--yes",
            )
            # Assert connection files created and the connection/deployment is set in flow.dag.yaml
            check_connection_and_deployment(flow_folder, connection=connection, deployment=deployment)
            connection_files = [flow_folder / "azure_openai.yaml", flow_folder / "openai.yaml"]
            for file in connection_files:
                assert file.exists()
                with open(file, "r") as f:
                    connection_dict = load_yaml(f)
                    assert connection_dict["name"] == connection

            shutil.rmtree(flow_folder)
            target = "promptflow._sdk._pf_client.Configuration.get_connection_provider"
            with mock.patch(target) as mocked:
                mocked.return_value = "azureml:xx"
                # When configure azure connection provider, init chat flow without connection and deployment.
                run_pf_command(
                    "flow",
                    "init",
                    "--flow",
                    flow_name,
                    "--type",
                    "chat",
                    "--yes",
                )
                # Assert connection files not created.
                assert not (flow_folder / "azure_openai.yaml").exists()
                assert not (flow_folder / "openai.yaml").exists()

                # When configure azure connection provider, init chat flow with connection and deployment.
                connection = "connection_name"
                deployment = "deployment_name"
                run_pf_command(
                    "flow",
                    "init",
                    "--flow",
                    flow_name,
                    "--type",
                    "chat",
                    "--connection",
                    connection,
                    "--deployment",
                    deployment,
                    "--yes",
                )
                # Assert connection files not created and the connection/deployment is set in flow.dag.yaml
                check_connection_and_deployment(flow_folder, connection=connection, deployment=deployment)
                assert not (flow_folder / "azure_openai.yaml").exists()
                assert not (flow_folder / "openai.yaml").exists()

    def test_flow_chat(self, monkeypatch, capsys):
        chat_list = ["hi", "what is chat gpt?"]

        def mock_input(*args, **kwargs):
            if chat_list:
                return chat_list.pop()
            else:
                raise KeyboardInterrupt()

        monkeypatch.setattr("builtins.input", mock_input)
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/chat_flow",
            "--interactive",
        )
        output_path = Path(FLOWS_DIR) / "chat_flow" / ".promptflow" / "chat.output.json"
        assert output_path.exists()
        detail_path = Path(FLOWS_DIR) / "chat_flow" / ".promptflow" / "chat.detail.json"
        assert detail_path.exists()

        chat_list = ["hi", "what is chat gpt?"]
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/chat_flow_with_python_node_streaming_output",
            "--interactive",
        )
        output_path = (
            Path(FLOWS_DIR) / "chat_flow_with_python_node_streaming_output" / ".promptflow" / "chat.output.json"
        )
        assert output_path.exists()
        detail_path = (
            Path(FLOWS_DIR) / "chat_flow_with_python_node_streaming_output" / ".promptflow" / "chat.detail.json"
        )
        assert detail_path.exists()

        # Validate terminal output
        chat_list = ["hi", "what is chat gpt?"]
        run_pf_command("flow", "test", "--flow", f"{FLOWS_DIR}/chat_flow", "--interactive", "--verbose")
        outerr = capsys.readouterr()
        # Check node output
        assert "chat_node:" in outerr.out
        assert "show_answer:" in outerr.out
        assert "[show_answer]: print:" in outerr.out

    def test_invalid_chat_flow(self, monkeypatch, capsys):
        def mock_input(*args, **kwargs):
            if chat_list:
                return chat_list.pop()
            else:
                raise KeyboardInterrupt()

        monkeypatch.setattr("builtins.input", mock_input)

        chat_list = ["hi", "what is chat gpt?"]
        with pytest.raises(SystemExit):
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/chat_flow_with_exception",
                "--interactive",
            )
        outerr = capsys.readouterr()
        assert "Execution failure in 'show_answer': (Exception) mock exception" in outerr.out
        output_path = Path(FLOWS_DIR) / "chat_flow" / ".promptflow" / "chat.output.json"
        assert output_path.exists()
        detail_path = Path(FLOWS_DIR) / "chat_flow" / ".promptflow" / "chat.detail.json"
        assert detail_path.exists()

        with pytest.raises(SystemExit):
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/chat_flow_with_multi_output_invalid",
                "--interactive",
            )
        outerr = capsys.readouterr()
        assert "chat flow does not support multiple chat outputs" in outerr.out

        with pytest.raises(SystemExit):
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/chat_flow_with_multi_input_invalid",
                "--interactive",
            )
        outerr = capsys.readouterr()
        assert "chat flow does not support multiple chat inputs" in outerr.out

        with pytest.raises(SystemExit):
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/chat_flow_with_invalid_output",
                "--interactive",
            )
        outerr = capsys.readouterr()
        assert "chat output is not configured" in outerr.out

    @pytest.mark.skipif(pytest.is_replay, reason="Cannot pass in replay mode")
    def test_chat_with_stream_output(self, monkeypatch, capsys):
        chat_list = ["hi", "what is chat gpt?"]

        def mock_input(*args, **kwargs):
            if chat_list:
                return chat_list.pop()
            else:
                raise KeyboardInterrupt()

        monkeypatch.setattr("builtins.input", mock_input)

        # Test streaming output
        chat_list = ["hi", "what is chat gpt?"]
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/chat_flow_with_stream_output",
            "--interactive",
        )
        output_path = Path(FLOWS_DIR) / "chat_flow_with_stream_output" / ".promptflow" / "chat.output.json"
        assert output_path.exists()
        detail_path = Path(FLOWS_DIR) / "chat_flow_with_stream_output" / ".promptflow" / "chat.detail.json"
        assert detail_path.exists()

        # Test prompty with stream output
        chat_list = ["What is the sum of the calculation results of previous rounds?", "what is the result of 3+3?"]
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{PROMPTY_DIR}/prompty_with_chat_history_and_stream_output.prompty",
            "--interactive",
        )
        outerr = capsys.readouterr()
        assert "6" in outerr.out
        assert "12" in outerr.out
        output_path = (
            Path(PROMPTY_DIR) / ".promptflow" / "prompty_with_chat_history_and_stream_output" / "chat.output.json"
        )
        assert output_path.exists()
        detail_path = (
            Path(PROMPTY_DIR) / ".promptflow" / "prompty_with_chat_history_and_stream_output" / "chat.detail.json"
        )
        assert detail_path.exists()

    def test_flow_test_with_default_chat_history(self):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/chat_flow_with_default_history",
        )
        output_path = Path(FLOWS_DIR) / "chat_flow_with_default_history" / ".promptflow" / "flow.output.json"
        assert output_path.exists()
        detail_path = Path(FLOWS_DIR) / "chat_flow_with_default_history" / ".promptflow" / "flow.detail.json"
        assert detail_path.exists()
        with open(detail_path, "r") as f:
            details = json.load(f)
        expect_chat_history = [
            {"inputs": {"question": "hi"}, "outputs": {"answer": "hi"}},
            {"inputs": {"question": "who are you"}, "outputs": {"answer": "who are you"}},
        ]
        assert details["flow_runs"][0]["inputs"]["chat_history"] == expect_chat_history

    def test_flow_test_with_user_defined_chat_history(self, monkeypatch, capsys):
        chat_list = ["hi", "what is chat gpt?"]

        def mock_input(*args, **kwargs):
            if chat_list:
                return chat_list.pop()
            else:
                raise KeyboardInterrupt()

        monkeypatch.setattr("builtins.input", mock_input)
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/chat_flow_with_defined_chat_history",
            "--interactive",
        )
        output_path = Path(FLOWS_DIR) / "chat_flow_with_defined_chat_history" / ".promptflow" / "chat.output.json"
        assert output_path.exists()
        detail_path = Path(FLOWS_DIR) / "chat_flow_with_defined_chat_history" / ".promptflow" / "chat.detail.json"
        assert detail_path.exists()

        # Test is_chat_history is set False
        with pytest.raises(SystemExit):
            chat_list = ["hi", "what is chat gpt?"]
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/chat_flow_without_defined_chat_history",
                "--interactive",
            )
        outerr = capsys.readouterr()
        assert "chat_history is required in the inputs of chat flow" in outerr.out

        chat_list = ["What is the sum of the calculation results of previous rounds?", "what is the result of 3+3?"]
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{PROMPTY_DIR}/prompty_with_chat_history.prompty",
            "--interactive",
        )
        outerr = capsys.readouterr()
        assert "6" in outerr.out
        assert "12" in outerr.out

    @pytest.mark.parametrize(
        "extra_args,expected_err",
        [
            pytest.param(
                [],
                "Required input(s) ['key'] are missing for \"flow\".",
                id="missing_required_flow_inputs",
            ),
            pytest.param(
                ["--node", "print_env"],
                "Required input(s) ['key'] are missing for \"print_env\".",
                id="missing_required_node_inputs",
            ),
        ],
    )
    def test_flow_test_inputs_missing(self, capsys, caplog, extra_args: List[str], expected_err: str):
        with pytest.raises(SystemExit):
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/print_env_var",
                "--environment-variables",
                "API_BASE=${azure_open_ai_connection.api_base}",
                *extra_args,
            )
        stdout, _ = capsys.readouterr()
        assert expected_err in stdout

    @pytest.mark.parametrize(
        "extra_args,expected_inputs,expected_log_prefixes",
        [
            pytest.param(
                [
                    "--inputs",
                    f"url={TARGET_URL}",
                    "answer=Channel",
                    "evidence=Url",
                ],
                [
                    {"answer": "Channel", "evidence": "Url"},
                    {"url": TARGET_URL, "answer": "Channel", "evidence": "Url"},
                ],
                [
                    "Unknown input(s) of flow: ",
                    "flow input(s): ",
                ],
                id="unknown_flow_inputs",
            ),
            pytest.param(
                [
                    "--inputs",
                    f"inputs.url={TARGET_URL}",
                    "unknown_input=unknown_val",
                    "--node",
                    "fetch_text_content_from_url",
                ],
                [
                    {"unknown_input": "unknown_val"},
                    {"fetch_url": TARGET_URL, "unknown_input": "unknown_val"},
                ],
                [
                    "Unknown input(s) of fetch_text_content_from_url: ",
                    "fetch_text_content_from_url input(s): ",
                ],
                id="unknown_inputs_node",
            ),
        ],
    )
    def test_flow_test_inputs_unknown(
        self, caplog, extra_args: List[str], expected_inputs: List[Dict[str, str]], expected_log_prefixes: List[str]
    ):
        logger = logging.getLogger(LOGGER_NAME)
        logger.propagate = True

        def validate_log(log_msg, prefix, expect_dict):
            log_inputs = json.loads(log_msg[len(prefix) :].replace("'", '"'))
            assert prefix in log_msg
            assert expect_dict == log_inputs

        with caplog.at_level(level=logging.WARNING, logger=LOGGER_NAME):
            run_pf_command("flow", "test", "--flow", f"{FLOWS_DIR}/web_classification", *extra_args)
            for log, expected_input, expected_log_prefix in zip(caplog.records, expected_inputs, expected_log_prefixes):
                validate_log(
                    prefix=expected_log_prefix,
                    log_msg=log.message,
                    expect_dict=expected_input,
                )

    def test_flow_build(self):
        source = f"{FLOWS_DIR}/web_classification_with_additional_include/flow.dag.yaml"
        output_path = "dist"

        def get_node_settings(_flow_dag_path: Path):
            flow_dag = load_yaml(_flow_dag_path)
            target_node = next(filter(lambda x: x["name"] == "summarize_text_content", flow_dag["nodes"]))
            target_node.pop("name")
            return target_node

        try:
            run_pf_command(
                "flow",
                "build",
                "--source",
                source,
                "--output",
                output_path,
                "--format",
                "docker",
                "--variant",
                "${summarize_text_content.variant_0}",
            )

            new_flow_dag_path = Path(output_path, "flow", "flow.dag.yaml")
            flow_dag = load_yaml(Path(source))
            assert (
                get_node_settings(new_flow_dag_path)
                == flow_dag["node_variants"]["summarize_text_content"]["variants"]["variant_0"]["node"]
            )
            assert get_node_settings(Path(source)) != get_node_settings(new_flow_dag_path)

            connection_path = Path(output_path, "connections", "azure_open_ai_connection.yaml")
            assert connection_path.exists()
        finally:
            shutil.rmtree(output_path, ignore_errors=True)

    def test_flex_flow_build(self):
        from promptflow._cli._pf.entry import main

        origin_build = Path(f"{FLOWS_DIR}/export/flex_flow_build")
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            cmd = (
                "pf",
                "flow",
                "build",
                "--source",
                f"{EAGER_FLOWS_DIR}/chat-basic/flow.flex.yaml",
                "--output",
                temp.as_posix(),
                "--format",
                "docker",
            )
            sys.argv = list(cmd)
            main()
            compare_directories(origin_build, temp, ("connections", ".promptflow", "__pycache__"))

    def test_flow_build_with_ua(self, capsys):
        with pytest.raises(SystemExit):
            run_pf_command(
                "flow",
                "build",
                "--source",
                "not_exist",
                "--output",
                "dist",
                "--format",
                "docker",
                "--user-agent",
                "test/1.0.0",
            )
            _, err = capsys.readouterr()
            assert "not exist" in err

    @pytest.mark.parametrize(
        "file_name, expected, update_item",
        [
            (
                "azure_openai_connection.yaml",
                {
                    "module": "promptflow.connections",
                    "type": "azure_open_ai",
                    "api_type": "azure",
                    "api_version": "2023-07-01-preview",
                    "api_key": SCRUBBED_VALUE,
                    "api_base": "aoai-api-endpoint",
                    "resource_id": "mock_id",
                },
                ("api_base", "new_value"),
            ),
            (
                "custom_connection.yaml",
                {
                    "module": "promptflow.connections",
                    "type": "custom",
                    "configs": {"key1": "test1"},
                    "secrets": {"key2": SCRUBBED_VALUE},
                },
                ("configs.key1", "new_value"),
            ),
            (
                "custom_strong_type_connection.yaml",
                {
                    "module": "promptflow.connections",
                    "type": "custom",
                    "configs": {
                        "api_base": "This is my first connection.",
                        "promptflow.connection.custom_type": "MyFirstConnection",
                        "promptflow.connection.module": "my_tool_package.connections",
                        "promptflow.connection.package": "test-custom-tools",
                        "promptflow.connection.package_version": "0.0.2",
                    },
                    "secrets": {"api_key": SCRUBBED_VALUE},
                },
                ("configs.api_base", "new_value"),
            ),
        ],
    )
    def test_connection_create_update(
        self, install_custom_tool_pkg, file_name, expected, update_item, capfd, local_client
    ):
        name = f"Connection_{str(uuid.uuid4())[:4]}"
        run_pf_command("connection", "create", "--file", f"{CONNECTIONS_DIR}/{file_name}", "--name", f"{name}")
        out, err = capfd.readouterr()
        # Assert in to skip some datetime fields
        assert expected.items() <= json.loads(out).items()

        # Update with --set
        update_key, update_value = update_item
        run_pf_command("connection", "update", "--set", f"{update_key}={update_value}", "--name", f"{name}")
        out, _ = capfd.readouterr()
        assert update_value in out, f"expected updated value {update_value} not in {out}"
        connection = local_client.connections.get(name)
        # Assert secrets are not scrubbed
        assert not any(v == SCRUBBED_VALUE for v in connection._secrets.values())

    def test_input_with_dict_val(self, pf):
        run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--file",
            "./input_with_dict_val.yaml",
            "--name",
            run_id,
            cwd=f"{RUNS_DIR}",
        )
        outputs = pf.runs._get_outputs(run=run_id)
        assert "dict" in outputs["output"][0]

    def test_visualize_ignore_space(self) -> None:
        names = ["a,b,c,d", "a, b, c, d", "a, b , c,  d"]
        groundtruth = ["a", "b", "c", "d"]

        def mocked_visualize(*args, **kwargs):
            runs = args[0]
            assert runs == groundtruth

        with patch.object(RunOperations, "visualize") as mock_visualize:
            mock_visualize.side_effect = mocked_visualize
            for name in names:
                run_pf_command(
                    "run",
                    "visualize",
                    "--names",
                    name,
                )

    def test_pf_run_with_stream_log(self, capfd):
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/flow_with_user_output",
            "--data",
            f"{DATAS_DIR}/webClassification3.jsonl",
            "--column-mapping",
            "key=value",
            "extra=${data.url}",
            "--stream",
        )
        out, _ = capfd.readouterr()
        # For Batch run, the executor uses bulk logger to print logs, and only prints the error log of the nodes.
        existing_keywords = ["execution", "execution.bulk", "WARNING", "error log"]
        non_existing_keywords = ["execution.flow", "user log"]
        for keyword in existing_keywords:
            assert keyword in out
        for keyword in non_existing_keywords:
            assert keyword not in out

    def test_pf_run_no_stream_log(self, capfd):
        # without --stream, logs will be in the run's log file

        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/flow_with_user_output",
            "--data",
            f"{DATAS_DIR}/webClassification3.jsonl",
            "--column-mapping",
            "key=value",
            "extra=${data.url}",
        )
        out, _ = capfd.readouterr()
        assert "user log" not in out
        assert "error log" not in out
        # flow logs won't stream
        assert "Executing node print_val. node run id:" not in out
        # executor logs won't stream
        assert "Node print_val completes." not in out

    def test_format_cli_exception(self, capsys):
        from promptflow._sdk.operations._connection_operations import ConnectionOperations

        with patch.dict(os.environ, {"PROMPTFLOW_STRUCTURE_EXCEPTION_OUTPUT": "true"}):
            with pytest.raises(SystemExit):
                run_pf_command(
                    "connection",
                    "show",
                    "--name",
                    "invalid_connection_name",
                )
            outerr = capsys.readouterr()
            assert outerr.err
            error_msg = json.loads(outerr.err)
            assert error_msg["code"] == "UserError"
            assert error_msg["innerError"]["innerError"]["code"] == "ConnectionNotFoundError"

            def mocked_connection_get(*args, **kwargs):
                raise Exception("mock exception")

            with patch.object(ConnectionOperations, "get") as mock_connection_get:
                mock_connection_get.side_effect = mocked_connection_get
                with pytest.raises(Exception):
                    run_pf_command(
                        "connection",
                        "show",
                        "--name",
                        "invalid_connection_name",
                    )
                outerr = capsys.readouterr()
                assert outerr.err
                error_msg = json.loads(outerr.err)
                assert error_msg["code"] == "SystemError"

        with pytest.raises(SystemExit):
            run_pf_command(
                "connection",
                "show",
                "--name",
                "invalid_connection_name",
            )
        outerr = capsys.readouterr()
        assert not outerr.err

    def test_tool_init(self, capsys):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_name = "package_name"
            func_name = "func_name"
            run_pf_command("tool", "init", "--package", package_name, "--tool", func_name, cwd=temp_dir)
            package_folder = Path(temp_dir) / package_name
            sys.path.append(str(package_folder.absolute()))
            assert (package_folder / package_name / f"{func_name}.py").exists()
            assert (package_folder / package_name / "utils.py").exists()
            assert (package_folder / package_name / "__init__.py").exists()
            assert (package_folder / "setup.py").exists()
            assert (package_folder / "README.md").exists()

            spec = importlib.util.spec_from_file_location(
                f"{package_name}.utils", package_folder / package_name / "utils.py"
            )
            utils = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(utils)

            assert hasattr(utils, "list_package_tools")
            tools_meta = utils.list_package_tools()
            assert f"{package_name}.{func_name}.{func_name}" in tools_meta
            meta = tools_meta[f"{package_name}.{func_name}.{func_name}"]
            assert meta["function"] == func_name
            assert meta["module"] == f"{package_name}.{func_name}"
            assert meta["name"] == func_name
            assert meta["description"] == f"This is {func_name} tool"
            assert meta["type"] == "python"

            # Invalid package/tool name
            invalid_package_name = "123-package-name"
            invalid_tool_name = "123_tool_name"
            with pytest.raises(SystemExit):
                run_pf_command("tool", "init", "--package", invalid_package_name, "--tool", func_name, cwd=temp_dir)
            outerr = capsys.readouterr()
            assert f"The package name {invalid_package_name} is a invalid identifier." in outerr.out
            with pytest.raises(SystemExit):
                run_pf_command("tool", "init", "--package", package_name, "--tool", invalid_tool_name, cwd=temp_dir)
            outerr = capsys.readouterr()
            assert f"The tool name {invalid_tool_name} is a invalid identifier." in outerr.out
            with pytest.raises(SystemExit):
                run_pf_command("tool", "init", "--tool", invalid_tool_name, cwd=temp_dir)
            outerr = capsys.readouterr()
            assert f"The tool name {invalid_tool_name} is a invalid identifier." in outerr.out

            # Test init package tool with extra info
            package_name = "tool_with_extra_info"
            package_folder = Path(temp_dir) / package_name
            package_folder.mkdir(exist_ok=True, parents=True)
            manifest_file = package_folder / "MANIFEST.in"
            mock_manifest_content = "include mock/path"
            with open(manifest_file, "w") as f:
                f.write(mock_manifest_content)

            icon_path = Path(DATAS_DIR) / "logo.jpg"
            category = "test_category"
            tags = {"tag1": "value1", "tag2": "value2"}
            run_pf_command(
                "tool",
                "init",
                "--package",
                package_name,
                "--tool",
                func_name,
                "--set",
                f"icon={icon_path.absolute()}",
                f"category={category}",
                f"tags={tags}",
                cwd=temp_dir,
            )
            with open(manifest_file, "r") as f:
                content = f.read()
                assert mock_manifest_content in content
                assert f"include {package_name}/icons" in content
            # Add a tool script with icon
            tool_script_name = "tool_func_with_icon"
            run_pf_command(
                "tool",
                "init",
                "--tool",
                tool_script_name,
                "--set",
                f"icon={icon_path.absolute()}",
                f"category={category}",
                f"tags={tags}",
                cwd=Path(temp_dir) / package_name / package_name,
            )

            sys.path.append(str(package_folder.absolute()))
            spec = importlib.util.spec_from_file_location(
                f"{package_name}.utils", package_folder / package_name / "utils.py"
            )
            utils = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(utils)

            assert hasattr(utils, "list_package_tools")
            tools_meta = utils.list_package_tools()
            meta = tools_meta[f"{package_name}.{func_name}.{func_name}"]
            assert meta["category"] == category
            assert meta["tags"] == tags
            assert meta["icon"].startswith("data:image")
            assert tools_meta[f"{package_name}.{tool_script_name}.{tool_script_name}"]["icon"].startswith("data:image")

            # icon doesn't exist
            with pytest.raises(SystemExit):
                run_pf_command(
                    "tool",
                    "init",
                    "--package",
                    package_name,
                    "--tool",
                    func_name,
                    "--set",
                    "icon=invalid_icon_path",
                    cwd=temp_dir,
                )
            outerr = capsys.readouterr()
            assert "Cannot find the icon path" in outerr.out

    @pytest.mark.skip("Enable after promptflow-tool depend on core")
    def test_list_tool_cache(self, caplog, mocker):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_name = "mock_tool_package_name"
            func_name = "func_name"
            run_pf_command("tool", "init", "--package", package_name, "--tool", func_name, cwd=temp_dir)
            package_folder = Path(temp_dir) / package_name

            # Package tool project
            subprocess.check_call([sys.executable, "setup.py", "sdist", "bdist_wheel"], cwd=package_folder)

            package_file = list((package_folder / "dist").glob("*.whl"))
            assert len(package_file) == 1
            # Install package
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", package_file[0].as_posix()], cwd=package_folder
            )

            package_module = importlib.import_module(package_name)
            # cache file in installed package
            assert (Path(package_module.__file__).parent / "yamls" / "tools_meta.yaml").exists()

            from mock_tool_package_name import utils

            # Get tools meta from cache file
            with caplog.at_level(level=logging.DEBUG, logger=utils.logger.name):
                tools_meta = utils.list_package_tools()
            assert "List tools meta from cache file" in caplog.text
            assert f"{package_name}.{func_name}.{func_name}" in tools_meta

    @pytest.mark.skip("Enable after promptflow-tool depend on core")
    def test_tool_list(self, capsys):
        # List package tools in environment
        run_pf_command("tool", "list")
        outerr = capsys.readouterr()
        tools_dict = json.loads(outerr.out)
        package_tool_name = "promptflow.tools.embedding.embedding"
        assert package_tool_name in tools_dict["package"]

        # List flow tools and package tools
        run_pf_command("tool", "list", "--flow", f"{FLOWS_DIR}/chat_flow")
        outerr = capsys.readouterr()
        tools_dict = json.loads(outerr.out)
        expect_flow_tools = {
            "chat.jinja2": {
                "type": "llm",
                "inputs": {"chat_history": {"type": ["string"]}, "question": {"type": ["string"]}},
                "source": "chat.jinja2",
            },
            "show_answer.py": {
                "type": "python",
                "inputs": {"chat_answer": {"type": ["string"]}},
                "source": "show_answer.py",
                "function": "show_answer",
            },
        }
        assert tools_dict["code"] == expect_flow_tools
        assert package_tool_name in tools_dict["package"]

        # Invalid flow parameter
        with pytest.raises(SystemExit):
            run_pf_command("tool", "list", "--flow", "invalid_flow_folder")
        outerr = capsys.readouterr()
        assert "invalid_flow_folder does not exist." in outerr.out

    def test_tool_validate(self):
        # Test validate tool script
        tool_script_path = Path(TOOL_ROOT) / "custom_llm_tool.py"
        run_pf_command("tool", "validate", "--source", str(tool_script_path))

        invalid_tool_script_path = Path(TOOL_ROOT) / "invalid_tool.py"
        with pytest.raises(SystemExit):
            run_pf_command("tool", "validate", "--source", str(invalid_tool_script_path))

        # Test validate package tool
        tool_script_path = Path(TOOL_ROOT) / "tool_package"
        sys.path.append(str(tool_script_path.resolve()))

        with patch("promptflow._sdk.operations._tool_operations.ToolOperations._is_package_tool", return_value=True):
            with pytest.raises(SystemExit):
                run_pf_command("tool", "validate", "--source", "tool_package")

        # Test validate tool in package
        with pytest.raises(SystemExit):
            run_pf_command("tool", "validate", "--source", "tool_package.invalid_tool.invalid_input_settings")

    def test_flow_test_with_image_input_and_output(self):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/python_tool_with_simple_image",
        )
        output_path = Path(FLOWS_DIR) / "python_tool_with_simple_image" / ".promptflow" / "output"
        assert output_path.exists()
        image_path = Path(FLOWS_DIR) / "python_tool_with_simple_image" / ".promptflow" / "intermediate"
        assert image_path.exists()

    def test_flow_test_with_composite_image(self):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/python_tool_with_composite_image",
        )
        output_path = Path(FLOWS_DIR) / "python_tool_with_composite_image" / ".promptflow" / "output"
        assert output_path.exists()
        image_path = Path(FLOWS_DIR) / "python_tool_with_composite_image" / ".promptflow" / "intermediate"
        assert image_path.exists()

    def test_flow_test_with_openai_vision_image_input_and_output(self):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/python_tool_with_openai_vision_image",
        )
        output_path = Path(FLOWS_DIR) / "python_tool_with_openai_vision_image" / ".promptflow" / "output"
        assert output_path.exists()
        image_path = Path(FLOWS_DIR) / "python_tool_with_openai_vision_image" / ".promptflow" / "intermediate"
        assert image_path.exists()

    def test_run_file_with_set(self, pf) -> None:
        name = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--file",
            f"{RUNS_DIR}/run_with_env.yaml",
            "--set",
            f"name={name}",
        )
        # run exists
        pf.runs.get(name=name)

    def test_run_file_with_set_priority(self, pf) -> None:
        # --name has higher priority than --set
        name1 = str(uuid.uuid4())
        name2 = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--file",
            f"{RUNS_DIR}/run_with_env.yaml",
            "--set",
            f"name={name1}",
            "--name",
            name2,
        )
        # run exists
        try:
            pf.runs.get(name=name1)
        except RunNotFoundError:
            pass
        pf.runs.get(name=name2)

    def test_data_scrubbing(self):
        # Prepare connection
        run_pf_command(
            "connection", "create", "--file", f"{CONNECTIONS_DIR}/custom_connection.yaml", "--name", "custom_connection"
        )

        # Test flow run
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/print_secret_flow",
        )
        output_path = Path(FLOWS_DIR) / "print_secret_flow" / ".promptflow" / "flow.output.json"
        assert output_path.exists()
        log_path = Path(FLOWS_DIR) / "print_secret_flow" / ".promptflow" / "flow.log"
        with open(log_path, "r") as f:
            log_content = f.read()
            assert "**data_scrubbed**" in log_content

        # Test node run
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/print_secret_flow",
            "--node",
            "print_secret",
            "--inputs",
            "conn=custom_connection",
            "inputs.topic=atom",
        )
        output_path = Path(FLOWS_DIR) / "print_secret_flow" / ".promptflow" / "flow-print_secret.node.detail.json"
        assert output_path.exists()
        log_path = Path(FLOWS_DIR) / "print_secret_flow" / ".promptflow" / "print_secret.node.log"
        with open(log_path, "r") as f:
            log_content = f.read()
        assert "**data_scrubbed**" in log_content

    def test_cli_ua(self, pf):
        # clear user agent before test
        context = OperationContext().get_instance()
        context.user_agent = ""
        with environment_variable_overwrite(PF_USER_AGENT, ""):
            with pytest.raises(SystemExit):
                run_pf_command(
                    "run",
                    "show",
                    "--name",
                    "not_exist",
                )
        user_agent = ClientUserAgentUtil.get_user_agent()
        ua_dict = parse_ua_to_dict(user_agent)
        assert ua_dict.keys() == {"promptflow-sdk", "promptflow-cli"}

    def test_config_set_pure_flow_directory_macro(self, capfd: pytest.CaptureFixture) -> None:
        run_pf_command(
            "config",
            "set",
            "run.output_path='${flow_directory}'",
        )
        out, _ = capfd.readouterr()
        expected_error_message = (
            "Invalid config value '${flow_directory}' for 'run.output_path': "
            "Cannot specify flow directory as run output path; "
            "if you want to specify run output path under flow directory, "
            "please use its child folder, e.g. '${flow_directory}/.runs'."
        )
        assert expected_error_message in out

        from promptflow._sdk._configuration import Configuration

        config = Configuration.get_instance()
        assert config.get_run_output_path() is None

    def test_user_agent_in_cli(self):
        context = OperationContext().get_instance()
        context.user_agent = ""
        with pytest.raises(SystemExit):
            run_pf_command(
                "run",
                "show",
                "--name",
                "not_exist",
                "--user-agent",
                "a/1.0.0 b/2.0",
            )
        user_agent = ClientUserAgentUtil.get_user_agent()
        ua_dict = parse_ua_to_dict(user_agent)
        assert ua_dict.keys() == {"promptflow-sdk", "promptflow-cli", "a", "b"}
        context.user_agent = ""

    def test_node_run_telemetry(self, local_client):
        from promptflow._sdk._telemetry.logging_handler import PromptFlowSDKLogHandler

        def assert_node_run(*args, **kwargs):
            record = args[0]
            assert record.msg.startswith("pf.flow.node_test") or record.msg.startswith("pf.flows.node_test")
            assert record.custom_dimensions["activity_name"] in ["pf.flow.node_test", "pf.flows.node_test"]

        def assert_flow_test(*args, **kwargs):
            record = args[0]
            assert record.msg.startswith("pf.flow.test") or record.msg.startswith("pf.flows.test")
            assert record.custom_dimensions["activity_name"] in ["pf.flow.test", "pf.flows.test"]

        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copytree((Path(FLOWS_DIR) / "print_env_var").resolve().as_posix(), temp_dir, dirs_exist_ok=True)

            with patch.object(PromptFlowSDKLogHandler, "emit") as mock_logger:
                mock_logger.side_effect = assert_node_run
                run_pf_command(
                    "flow",
                    "test",
                    "--flow",
                    temp_dir,
                    "--inputs",
                    "key=API_BASE",
                    "--node",
                    "print_env",
                )

            with patch.object(PromptFlowSDKLogHandler, "emit") as mock_logger:
                mock_logger.side_effect = assert_flow_test
                run_pf_command(
                    "flow",
                    "test",
                    "--flow",
                    temp_dir,
                    "--inputs",
                    "key=API_BASE",
                )

    def test_run_create_with_existing_run_folder(self):
        run_name = "web_classification_variant_0_20231205_120253_104100"
        # clean the run if exists
        from promptflow._cli._utils import _try_delete_existing_run_record
        from promptflow.client import PFClient

        pf = PFClient()
        _try_delete_existing_run_record(run_name)

        # assert the run doesn't exist
        with pytest.raises(RunNotFoundError):
            pf.runs.get(run_name)

        uuid_str = str(uuid.uuid4())
        run_folder = Path(RUNS_DIR) / run_name
        run_pf_command(
            "run",
            "create",
            "--source",
            Path(run_folder).resolve().as_posix(),
            "--set",
            f"display_name={uuid_str}",
            f"description={uuid_str}",
            f"tags.tag1={uuid_str}",
        )

        # check run results
        run = pf.runs.get(run_name)
        assert run.display_name == uuid_str
        assert run.description == uuid_str
        assert run.tags["tag1"] == uuid_str

    def test_cli_command_no_sub_command(self, capfd):
        try:
            run_pf_command(
                "run",
            )
            # argparse will return SystemExit after running --help
        except SystemExit:
            pass
        # will run pf run -h
        out, _ = capfd.readouterr()
        assert "A CLI tool to manage runs for prompt flow." in out

        try:
            run_pf_command("run", "-h")
            # argparse will return SystemExit after running --help
        except SystemExit:
            pass
        # will run pf run -h
        out, _ = capfd.readouterr()
        assert "A CLI tool to manage runs for prompt flow." in out

    def test_unknown_command(self, capfd):
        try:
            run_pf_command(
                "unknown",
            )
            # argparse will return SystemExit after running --help
        except SystemExit:
            pass
        _, err = capfd.readouterr()
        assert "invalid choice" in err

    def test_config_set_user_agent(self) -> None:
        run_pf_command(
            "config",
            "set",
            "user_agent=test/1.0.0",
        )
        user_agent = setup_user_agent_to_operation_context(None)
        ua_dict = parse_ua_to_dict(user_agent)
        assert ua_dict.keys() == {"promptflow-sdk", "promptflow-cli", "PFCustomer_test"}

        # clear user agent
        run_pf_command(
            "config",
            "set",
            "user_agent=",
        )
        context = OperationContext().get_instance()
        context.user_agent = ""

    def test_basic_flow_run_delete(self, monkeypatch, local_client, capfd) -> None:
        input_list = ["y"]

        def mock_input(*args, **kwargs):
            if input_list:
                return input_list.pop()
            else:
                raise KeyboardInterrupt()

        monkeypatch.setattr("builtins.input", mock_input)

        run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--name",
            run_id,
            "--flow",
            f"{FLOWS_DIR}/print_env_var",
            "--data",
            f"{DATAS_DIR}/env_var_names.jsonl",
        )
        out, _ = capfd.readouterr()
        assert "Completed" in out

        run_a = local_client.runs.get(name=run_id)
        local_storage = LocalStorageOperations(run_a)
        path_a = local_storage.path
        assert os.path.exists(path_a)

        # delete the run
        run_pf_command(
            "run",
            "delete",
            "--name",
            f"{run_id}",
        )
        # both runs are deleted and their folders are deleted
        assert not os.path.exists(path_a)

    def test_basic_flow_run_delete_no_confirm(self, monkeypatch, local_client, capfd) -> None:
        run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--name",
            run_id,
            "--flow",
            f"{FLOWS_DIR}/print_env_var",
            "--data",
            f"{DATAS_DIR}/env_var_names.jsonl",
        )
        out, _ = capfd.readouterr()
        assert "Completed" in out

        run_a = local_client.runs.get(name=run_id)
        local_storage = LocalStorageOperations(run_a)
        path_a = local_storage.path
        assert os.path.exists(path_a)

        # delete the run
        run_pf_command("run", "delete", "--name", f"{run_id}", "-y")

        # both runs are deleted and their folders are deleted
        assert not os.path.exists(path_a)

    def test_basic_flow_run_delete_error(self, monkeypatch) -> None:
        input_list = ["y"]

        def mock_input(*args, **kwargs):
            if input_list:
                return input_list.pop()
            else:
                raise KeyboardInterrupt()

        monkeypatch.setattr("builtins.input", mock_input)
        run_id = str(uuid.uuid4())

        # delete the run
        with pytest.raises(SystemExit):
            run_pf_command(
                "run",
                "delete",
                "--name",
                f"{run_id}",
            )

    def test_experiment_hide_by_default(self, monkeypatch, capfd):
        # experiment will be hide if no config set
        with pytest.raises(SystemExit):
            run_pf_command(
                "experiment",
                "create",
                "--template",
                f"{EXPERIMENT_DIR}/basic-no-script-template/basic.exp.yaml",
            )

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Injection cannot passed to detach process.")
    @pytest.mark.usefixtures("setup_experiment_table")
    def test_experiment_start(self, monkeypatch, capfd, local_client):
        def wait_for_experiment_terminated(experiment_name):
            experiment = local_client._experiments.get(experiment_name)
            while experiment.status in [ExperimentStatus.IN_PROGRESS, ExperimentStatus.QUEUING]:
                sleep(10)
                experiment = local_client._experiments.get(experiment_name)
            return experiment

        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            exp_name = str(uuid.uuid4())
            run_pf_command(
                "experiment",
                "create",
                "--template",
                f"{EXPERIMENT_DIR}/basic-script-template/basic-script.exp.yaml",
                "--name",
                exp_name,
            )
            out, _ = capfd.readouterr()
            assert exp_name in out
            assert ExperimentStatus.NOT_STARTED in out

            run_pf_command(
                "experiment",
                "start",
                "--name",
                exp_name,
            )
            out, _ = capfd.readouterr()
            assert ExperimentStatus.QUEUING in out
            wait_for_experiment_terminated(exp_name)
            exp = local_client._experiments.get(name=exp_name)
            assert len(exp.node_runs) == 4
            assert all(len(exp.node_runs[node_name]) > 0 for node_name in exp.node_runs)
            metrics = local_client.runs.get_metrics(name=exp.node_runs["eval"][0]["name"])
            assert "accuracy" in metrics

    @pytest.mark.skipif(condition=not pytest.is_live, reason="Injection cannot passed to detach process.")
    @pytest.mark.usefixtures("setup_experiment_table")
    def test_experiment_start_anonymous_experiment(self, monkeypatch, local_client):
        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            from promptflow._sdk.entities._experiment import Experiment

            with mock.patch.object(Experiment, "_generate_name") as mock_generate_name:
                experiment_name = str(uuid.uuid4())
                mock_generate_name.return_value = experiment_name
                mock_func.return_value = True
                experiment_file = f"{EXPERIMENT_DIR}/basic-script-template/basic-script.exp.yaml"
                run_pf_command("experiment", "start", "--template", experiment_file, "--stream")
                exp = local_client._experiments.get(name=experiment_name)
                assert len(exp.node_runs) == 4
                assert all(len(exp.node_runs[node_name]) > 0 for node_name in exp.node_runs)
                metrics = local_client.runs.get_metrics(name=exp.node_runs["eval"][0]["name"])
                assert "accuracy" in metrics

    @pytest.mark.usefixtures("setup_experiment_table", "recording_injection")
    def test_experiment_test(self, monkeypatch, capfd, local_client, tmpdir):
        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/web_classification",
                "--experiment",
                f"{EXPERIMENT_DIR}/basic-no-script-template/basic.exp.yaml",
                "--detail",
                Path(tmpdir).as_posix(),
            )
            out, _ = capfd.readouterr()
            assert "main" in out
            assert "eval" in out

        for filename in ["flow.detail.json", "flow.output.json", "flow.log"]:
            for node_name in ["main", "eval"]:
                path = Path(tmpdir) / node_name / filename
                assert path.is_file()

    @pytest.mark.usefixtures("setup_experiment_table", "recording_injection")
    def test_experiment_direct_test(self, monkeypatch, capfd, local_client, tmpdir):
        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            run_pf_command(
                "experiment",
                "test",
                "--template",
                f"{EXPERIMENT_DIR}/basic-no-script-template/basic.exp.yaml",
            )
            out, _ = capfd.readouterr()
            assert "main" in out
            assert "eval" in out

    def test_run_list(self, local_client):
        from promptflow._sdk.entities import Run

        with patch.object(Run, "_to_dict") as mock_to_dict:
            mock_to_dict.side_effect = RuntimeError("mock exception")
            run_pf_command(
                "run",
                "list",
            )

    def test_pf_flow_test_with_detail(self, tmpdir):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--inputs",
            "url=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
            "answer=Channel",
            "evidence=Url",
            "--detail",
            Path(tmpdir).as_posix(),
        )
        # when specify parameter `detail`, detail, output and log will be saved in
        # the specified folder
        for filename in ["flow.detail.json", "flow.output.json", "flow.log"]:
            path = Path(tmpdir) / filename
            assert path.is_file()

    def test_pf_flow_test_single_node_with_detail(self, tmpdir):
        node_name = "fetch_text_content_from_url"
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--inputs",
            "inputs.url="
            "https://www.microsoft.com/en-us/d/xbox-wireless-controller-stellar-shift-special-edition/94fbjc7h0h6h",
            "--node",
            node_name,
            "--detail",
            Path(tmpdir).as_posix(),
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / f"flow-{node_name}.node.detail.json"
        assert output_path.exists()

        # when specify parameter `detail`, node detail, output and log will be saved in
        # the specified folder
        for filename in [
            f"flow-{node_name}.node.detail.json",
            f"flow-{node_name}.node.output.json",
            f"{node_name}.node.log",
        ]:
            path = Path(tmpdir) / filename
            assert path.is_file()

    def test_flow_run_resume_from(self, local_client) -> None:
        run_id = str(uuid.uuid4())
        # fetch std out
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--data",
            f"{DATAS_DIR}/webClassification3.jsonl",
            "--name",
            run_id,
        )
        original_run = local_client.runs.get(name=run_id)
        assert original_run.status == "Completed"
        output_path = os.path.join(original_run.properties["output_path"], "flow_outputs", "output.jsonl")
        with open(output_path, "r") as file:
            original_output = [json.loads(line) for line in file]
        # Since the data have 15 lines, we can assume the original run has succeeded lines in over 99% cases
        original_success_count = len(original_output)

        new_run_id = str(uuid.uuid4())
        display_name = "test"
        description = "new description"
        run_pf_command(
            "run",
            "create",
            "--resume-from",
            run_id,
            "--name",
            new_run_id,
            "--set",
            f"display_name={display_name}",
            f"description={description}",
            "tags.A=A",
            "tags.B=B",
        )
        resume_run = local_client.runs.get(name=new_run_id)
        assert resume_run.name == new_run_id
        assert resume_run.display_name == display_name
        assert resume_run.description == description
        assert resume_run.tags == {"A": "A", "B": "B"}
        assert resume_run._resume_from == run_id
        # assert new run resume from the original run
        output_path = os.path.join(resume_run.properties["output_path"], "flow_outputs", "output.jsonl")
        with open(output_path, "r") as file:
            resume_output = [json.loads(line) for line in file]
        assert len(resume_output) == len(original_output)

        log_path = os.path.join(resume_run.properties["output_path"], "logs.txt")
        with open(log_path, "r") as file:
            log_text = file.read()
        assert f"Skipped the execution of {original_success_count} existing results." in log_text

    def test_flow_run_resume_partially_failed_run(self, capfd, local_client) -> None:
        run_id = str(uuid.uuid4())
        data_path = f"{DATAS_DIR}/simple_hello_world_multi_lines.jsonl"
        with open(data_path, "r") as f:
            total_lines = len(f.readlines())
        # fetch std out
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/simple_hello_world_random_fail",
            "--data",
            data_path,
            "--name",
            run_id,
        )
        out, _ = capfd.readouterr()
        assert "Completed" in out

        def get_successful_lines(output_path):
            with open(Path(output_path) / "outputs.jsonl", "r") as f:
                return set(map(lambda x: x[LINE_NUMBER_KEY], map(json.loads, f.readlines())))

        completed_line_set = set()
        while True:
            run = local_client.runs.get(name=run_id)
            new_completed_line_set = get_successful_lines(run.properties["output_path"])
            if len(new_completed_line_set) == total_lines:
                break
            assert new_completed_line_set.issuperset(completed_line_set), "successful lines should be increasing"
            completed_line_set = new_completed_line_set

            new_run_id = str(uuid.uuid4())
            run_pf_command(
                "run",
                "create",
                "--resume-from",
                run_id,
                "--name",
                new_run_id,
            )
            run_id = new_run_id

    def test_flow_run_resume_from_token(self, local_client) -> None:
        run_id = str(uuid.uuid4())
        # fetch std out
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/web_classification_random_fail",
            "--data",
            f"{FLOWS_DIR}/web_classification_random_fail/data.jsonl",
            "--column-mapping",
            "url='${data.url}'",
            "--name",
            run_id,
        )
        original_run = local_client.runs.get(name=run_id)
        assert original_run.status == "Completed"
        output_path = os.path.join(original_run.properties["output_path"], "flow_outputs", "output.jsonl")
        with open(output_path, "r") as file:
            original_output = [json.loads(line) for line in file]
        # Since the data have 15 lines, we can assume the original run has succeeded lines in over 99% cases
        original_success_count = len(original_output)

        new_run_id = str(uuid.uuid4())
        display_name = "test"
        description = "new description"
        run_pf_command(
            "run",
            "create",
            "--resume-from",
            run_id,
            "--name",
            new_run_id,
            "--set",
            f"display_name={display_name}",
            f"description={description}",
            "tags.A=A",
            "tags.B=B",
        )
        resume_run = local_client.runs.get(name=new_run_id)
        assert resume_run.name == new_run_id
        assert resume_run.display_name == display_name
        assert resume_run.description == description
        assert resume_run.tags == {"A": "A", "B": "B"}
        assert resume_run._resume_from == run_id

        # assert new run resume from the original run
        output_path = os.path.join(resume_run.properties["output_path"], "flow_outputs", "output.jsonl")
        with open(output_path, "r") as file:
            resume_output = [json.loads(line) for line in file]
        assert len(resume_output) > len(original_output)

        log_path = os.path.join(resume_run.properties["output_path"], "logs.txt")
        with open(log_path, "r") as file:
            log_text = file.read()
        assert f"Skipped the execution of {original_success_count} existing results." in log_text

        # assert new run consumes more token than the original run
        assert (
            original_run.properties["system_metrics"]["total_tokens"]
            < resume_run.properties["system_metrics"]["total_tokens"]
        )

    def test_flow_run_resume_with_image_aggregation(self, local_client) -> None:
        metrics = {}

        def test_metric_logger(key, value):
            metrics[key] = value

        add_metric_logger(test_metric_logger)

        run_id = str(uuid.uuid4())
        # fetch std out
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/eval_flow_with_image_resume_random_fail",
            "--data",
            f"{FLOWS_DIR}/eval_flow_with_image_resume_random_fail/data.jsonl",
            "--column-mapping",
            "input_image='${data.input_image}'",
            "--name",
            run_id,
        )
        original_run = local_client.runs.get(name=run_id)
        assert original_run.status == "Completed"
        output_path = os.path.join(original_run.properties["output_path"], "flow_outputs", "output.jsonl")
        with open(output_path, "r") as file:
            original_output = [json.loads(line) for line in file]
        original_success_count = len(original_output)
        original_image_count = metrics.get("image_count", None)

        new_run_id = str(uuid.uuid4())
        display_name = "test"
        description = "new description"
        run_pf_command(
            "run",
            "create",
            "--resume-from",
            run_id,
            "--name",
            new_run_id,
            "--set",
            f"display_name={display_name}",
            f"description={description}",
            "tags.A=A",
            "tags.B=B",
        )
        resume_run = local_client.runs.get(name=new_run_id)
        resume_image_count = metrics.get("image_count", None)
        assert resume_run.name == new_run_id
        assert resume_run.display_name == display_name
        assert resume_run.description == description
        assert resume_run.tags == {"A": "A", "B": "B"}
        assert resume_run._resume_from == run_id

        # assert new run resume from the original run
        output_path = os.path.join(resume_run.properties["output_path"], "flow_outputs", "output.jsonl")
        with open(output_path, "r") as file:
            resume_output = [json.loads(line) for line in file]
        assert len(resume_output) > len(original_output)

        log_path = os.path.join(resume_run.properties["output_path"], "logs.txt")
        with open(log_path, "r") as file:
            log_text = file.read()
        assert f"Skipped the execution of {original_success_count} existing results." in log_text

        # assert aggregation node works
        assert original_image_count < resume_image_count

    def test_flow_run_exclusive_param(self, capfd) -> None:
        # fetch std out
        with pytest.raises(SystemExit):
            run_pf_command(
                "run",
                "create",
                "--flow",
                f"{FLOWS_DIR}/web_classification",
                "--resume-from",
                "mock",
            )
        out, _ = capfd.readouterr()
        assert "More than one is provided for exclusive options" in out

    def test_pf_test_interactive_with_non_string_streaming_output(self, monkeypatch, capsys):
        flow_dir = Path(f"{FLOWS_DIR}/chat_flow_with_non_string_stream_output")
        # mock user input with pop so make chat list reversed
        chat_list = ["what is chat gpt?", "hi"]

        def mock_input(*args, **kwargs):
            if chat_list:
                return chat_list.pop()
            else:
                raise KeyboardInterrupt()

        monkeypatch.setattr("builtins.input", mock_input)
        run_pf_command(
            "flow",
            "test",
            "--flow",
            flow_dir.as_posix(),
            "--interactive",
            "--verbose",
        )
        output_path = Path(flow_dir) / ".promptflow" / "chat.output.json"
        assert output_path.exists()
        detail_path = Path(flow_dir) / ".promptflow" / "chat.detail.json"
        assert detail_path.exists()

    def test_flow_test_prompty(self):
        prompty_path = Path(PROMPTY_DIR) / "prompty_example.prompty"
        run_pf_command("flow", "test", "--flow", prompty_path.as_posix(), "--inputs", 'question="who are you"')
        output_path = Path(prompty_path).parent / ".promptflow" / "prompty_example"
        assert output_path.exists()
        assert (output_path / "flow.log").exists()
        assert (output_path / "flow.detail.json").exists()
        assert (output_path / "flow.output.json").exists()

    def test_flow_run_prompty(self, capfd):
        prompty_path = Path(PROMPTY_DIR) / "prompty_example.prompty"

        run_pf_command(
            "run",
            "create",
            "--flow",
            prompty_path.as_posix(),
            "--data",
            f"{DATAS_DIR}/prompty_inputs.jsonl",
            "--name",
            str(uuid.uuid4()),
        )
        out, _ = capfd.readouterr()
        assert "Completed" in out

    def test_pf_run_with_init(self, pf):
        run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{EAGER_FLOWS_DIR}/basic_callable_class",
            "--data",
            f"{EAGER_FLOWS_DIR}/basic_callable_class/inputs.jsonl",
            "--name",
            run_id,
            "--init",
            "obj_input=val",
        )

        def assert_func(details_dict):
            return details_dict["outputs.func_input"] == [
                "func_input",
                "func_input",
                "func_input",
                "func_input",
            ] and details_dict["outputs.obj_input"] == ["val", "val", "val", "val"]

        # check run results
        run = pf.runs.get(run_id)
        assert_batch_run_result(run, pf, assert_func)

    def test_pf_run_with_init_resume(self, pf):
        original_run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{EAGER_FLOWS_DIR}/basic_callable_class",
            "--data",
            f"{EAGER_FLOWS_DIR}/basic_callable_class/inputs.jsonl",
            "--name",
            original_run_id,
            "--init",
            "obj_input=val",
        )

        def assert_func(details_dict):
            return details_dict["outputs.func_input"] == [
                "func_input",
                "func_input",
                "func_input",
                "func_input",
            ] and details_dict["outputs.obj_input"] == ["val", "val", "val", "val"]

        # check run results
        run = pf.runs.get(original_run_id)
        assert run.status == "Completed"
        assert_batch_run_result(run, pf, assert_func)

        resume_run_id_fail = str(uuid.uuid4())
        with pytest.raises(ValueError):
            run_pf_command(
                "run",
                "create",
                "--resume-from",
                original_run_id,
                "--name",
                resume_run_id_fail,
                "--init",
                "obj_input=val",
            )

        resume_run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--resume-from",
            original_run_id,
            "--name",
            resume_run_id,
        )
        resume_run = pf.runs.get(resume_run_id)
        assert resume_run.status == "Completed"
        assert_batch_run_result(resume_run, pf, assert_func)

    def test_pf_flow_save(self, pf):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_pf_command(
                "flow",
                "save",
                "--path",
                temp_dir,
                "--entry",
                "hello:hello_world",
                "--code",
                f"{EAGER_FLOWS_DIR}/../functions/hello_world",
            )
            assert set(os.listdir(temp_dir)) == {FLOW_FLEX_YAML, "hello.py"}
            content = load_yaml(Path(temp_dir) / FLOW_FLEX_YAML)
            assert content == {
                "entry": "hello:hello_world",
                "inputs": {
                    "text": {
                        "type": "string",
                    }
                },
            }
            os.unlink(Path(temp_dir) / FLOW_FLEX_YAML)
            run_pf_command(
                "flow",
                "save",
                "--entry",
                "hello:hello_world",
                cwd=temp_dir,
            )
            # __pycache__ will be created when inspecting the module
            assert set(os.listdir(temp_dir)) == {FLOW_FLEX_YAML, "hello.py", "__pycache__"}
            new_content = load_yaml(Path(temp_dir) / FLOW_FLEX_YAML)
            assert new_content == content

    def test_flow_test_with_init(self, pf, capsys):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{EAGER_FLOWS_DIR}/basic_callable_class",
            "--inputs",
            "func_input=input",
            "--init",
            "obj_input=val",
        )
        stdout, _ = capsys.readouterr()
        assert "obj_input" in stdout
        assert "func_input" in stdout

    def test_eager_flow_test_without_yaml(self, pf, capsys):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            "entry:my_flow",
            "--inputs",
            "input_val=val1",
            cwd=f"{EAGER_FLOWS_DIR}/simple_without_yaml_return_output",
        )
        stdout, _ = capsys.readouterr()
        assert "Hello world" in stdout
        assert "val1" in stdout

    def test_class_based_eager_flow_test_without_yaml(self, pf, capsys):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            "callable_without_yaml:MyFlow",
            "--inputs",
            "func_input=input",
            "--init",
            "obj_input=val",
            cwd=f"{EAGER_FLOWS_DIR}/basic_callable_class_without_yaml",
        )
        stdout, _ = capsys.readouterr()
        assert "obj_input" in stdout
        assert "func_input" in stdout

        run_pf_command(
            "flow",
            "test",
            "--flow",
            "callable_without_yaml:MyFlow",
            "--inputs",
            f"{EAGER_FLOWS_DIR}/basic_callable_class_without_yaml/inputs.jsonl",
            "--init",
            f"{EAGER_FLOWS_DIR}/basic_callable_class_without_yaml/init.json",
            cwd=f"{EAGER_FLOWS_DIR}/basic_callable_class_without_yaml",
        )
        stdout, _ = capsys.readouterr()
        assert "obj_input" in stdout
        assert "func_input" in stdout

        target = "promptflow._sdk._tracing.TraceDestinationConfig.need_to_resolve"
        with mock.patch(target) as mocked:
            mocked.return_value = True
            # When configure azure trace provider, will raise ConfigFileNotFound error since no config.json in code
            # folder.
            with pytest.raises(SystemExit):
                run_pf_command(
                    "flow",
                    "test",
                    "--flow",
                    "callable_without_yaml:MyFlow",
                    "--inputs",
                    f"{EAGER_FLOWS_DIR}/basic_callable_class_without_yaml/inputs.jsonl",
                    "--init",
                    f"{EAGER_FLOWS_DIR}/basic_callable_class_without_yaml/init.json",
                    cwd=f"{EAGER_FLOWS_DIR}/basic_callable_class_without_yaml",
                )
            out, _ = capsys.readouterr()
            assert "basic_callable_class_without_yaml" in out

    @pytest.mark.skip(reason="Chat UI won't exit automatically now and need to update this test")
    def test_eager_flow_test_without_yaml_ui(self, pf, capsys):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            "entry:my_flow",
            "--ui",
            cwd=f"{EAGER_FLOWS_DIR}/simple_without_yaml_return_output",
        )
        stdout, _ = capsys.readouterr()
        assert "You can begin chat flow" in stdout
        assert not Path(f"{EAGER_FLOWS_DIR}/simple_without_yaml_return_output/flow.flex.yaml").exists()

    @pytest.mark.usefixtures("reset_tracer_provider")
    def test_pf_flow_test_with_collection(self):
        with mock.patch("promptflow._sdk._configuration.Configuration.is_internal_features_enabled") as mock_func:
            mock_func.return_value = True
            collection = str(uuid.uuid4())
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/web_classification",
                "--inputs",
                "url=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
                "answer=Channel",
                "evidence=Url",
                "--collection",
                collection,
            )
            tracer_provider: TracerProvider = trace.get_tracer_provider()
            assert tracer_provider.resource.attributes["collection"] == collection

    def test_prompty_test_with_sample_file(self, capsys):

        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{PROMPTY_DIR}/prompty_example_with_sample.prompty",
        )
        outerr = capsys.readouterr()
        assert "2" in outerr.out

        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{PROMPTY_DIR}/prompty_example.prompty",
            "--inputs",
            f"{DATAS_DIR}/prompty_inputs.json",
        )
        outerr = capsys.readouterr()
        assert "2" in outerr.out

        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{PROMPTY_DIR}/prompty_example.prompty",
            "--inputs",
            f"{DATAS_DIR}/prompty_inputs.jsonl",
        )
        outerr = capsys.readouterr()
        assert "2" in outerr.out

        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{PROMPTY_DIR}/prompty_example.prompty",
            "--inputs",
            'question="what is the result of 1+1?"',
        )
        outerr = capsys.readouterr()
        assert "2" in outerr.out

        with pytest.raises(ValueError) as ex:
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{PROMPTY_DIR}/prompty_example.prompty",
                "--inputs",
                f"{DATAS_DIR}/invalid_path.json",
            )
        assert "Cannot find inputs file" in ex.value.args[0]

        with pytest.raises(ValueError) as ex:
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{PROMPTY_DIR}/prompty_example.prompty",
                "--inputs",
                f"{DATAS_DIR}/logo.jpg",
            )
        assert "Only support jsonl or json file as input" in ex.value.args[0]

    def test_pf_run_without_yaml(self, pf):
        run_id = str(uuid.uuid4())
        with inject_sys_path(f"{EAGER_FLOWS_DIR}/basic_callable_class"):
            run_pf_command(
                "run",
                "create",
                "--flow",
                "simple_callable_class:MyFlow",
                "--data",
                f"{EAGER_FLOWS_DIR}/basic_callable_class/inputs.jsonl",
                "--name",
                run_id,
                "--init",
                "obj_input=val",
                cwd=f"{EAGER_FLOWS_DIR}/basic_callable_class",
            )

        def assert_func(details_dict):
            return details_dict["outputs.func_input"] == [
                "func_input",
                "func_input",
                "func_input",
                "func_input",
            ] and details_dict["outputs.obj_input"] == ["val", "val", "val", "val"]

        # check run results
        run = pf.runs.get(run_id)
        assert_batch_run_result(run, pf, assert_func)

    def test_prompty_with_env(self, dev_connections, capfd):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            aoai_connection = dev_connections.get("azure_open_ai_connection")
            env = {
                "MOCK_AZURE_DEVELOPMENT": "gpt-35-turbo",
                "MOCK_AZURE_API_KEY": aoai_connection["value"]["api_key"],
                "MOCK_AZURE_API_VERSION": aoai_connection["value"]["api_version"],
                "MOCK_AZURE_ENDPOINT": aoai_connection["value"]["api_base"],
            }
            with open(env_file, "w") as f:
                f.writelines([f"{key}={value}\n" for key, value in env.items()])

            # Prompty test with default .env
            shutil.copy(f"{PROMPTY_DIR}/prompty_with_env.prompty", Path(temp_dir) / "prompty_with_env.prompty")
            with _change_working_dir(temp_dir):
                run_pf_command(
                    "flow",
                    "test",
                    "--flow",
                    f"{temp_dir}/prompty_with_env.prompty",
                    "--inputs",
                    'question="what is the result of 1+1?"',
                    "--env",
                )
            out, _ = capfd.readouterr()
            assert "2" in out

            # Prompty test with env file
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{PROMPTY_DIR}/prompty_with_env.prompty",
                "--inputs",
                'question="what is the result of 1+1?"',
                "--env",
                str(env_file),
            )
            out, _ = capfd.readouterr()
            assert "2" in out

            # prompty test with env dict
            env_params = [f"{key}={value}" for key, value in env.items()]
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{PROMPTY_DIR}/prompty_with_env.prompty",
                "--inputs",
                'question="what is the result of 1+1?"',
                "--env",
                *env_params,
            )
            out, _ = capfd.readouterr()
            assert "2" in out

            # Prompty test with env override
            invalid_env_file = Path(temp_dir) / "invalid.env"
            with open(invalid_env_file, "w") as f:
                f.writelines([f"{key}={value}\n" for key, value in env.items() if key != "MOCK_AZURE_API_KEY"])
                f.write("MOCK_AZURE_API_KEY=invalid_api_key")
            run_pf_command(
                "flow",
                "test",
                "--flow",
                f"{PROMPTY_DIR}/prompty_with_env.prompty",
                "--inputs",
                'question="what is the result of 1+1?"',
                "--env",
                str(env_file),
                f"MOCK_AZURE_API_KEY={env['MOCK_AZURE_API_KEY']}",
            )
            out, _ = capfd.readouterr()
            assert "2" in out

            with pytest.raises(Exception) as ex:
                run_pf_command(
                    "flow",
                    "test",
                    "--flow",
                    f"{PROMPTY_DIR}/prompty_with_env.prompty",
                    "--inputs",
                    'question="what is the result of 1+1?"',
                    "--env",
                    "invalid_path.env",
                )
            assert "cannot find the file" in str(ex.value)

            with pytest.raises(Exception) as ex:
                run_pf_command(
                    "flow",
                    "test",
                    "--flow",
                    f"{PROMPTY_DIR}/prompty_with_env.prompty",
                    "--inputs",
                    'question="what is the result of 1+1?"',
                    "--env",
                    "invalid_path.txt",
                )
            assert "expects file path endswith .env or KEY=VALUE [KEY=VALUE ...]" in str(ex.value)

            # Test batch run
            run_pf_command(
                "run",
                "create",
                "--flow",
                f"{PROMPTY_DIR}/prompty_with_env.prompty",
                "--data",
                f"{DATAS_DIR}/prompty_inputs.jsonl",
                "--env",
                str(env_file),
            )
            out, _ = capfd.readouterr()
            assert "Completed" in out

            # Test batch run
            run_pf_command(
                "run",
                "create",
                "--flow",
                f"{PROMPTY_DIR}/prompty_with_env.prompty",
                "--data",
                f"{DATAS_DIR}/prompty_inputs.jsonl",
                "--env",
                *env_params,
            )
            out, _ = capfd.readouterr()
            assert "Completed" in out


def assert_batch_run_result(run, pf, assert_func):
    assert run.status == "Completed"
    assert "error" not in run._to_dict(), run._to_dict()["error"]
    details = pf.get_details(run.name)
    # convert DataFrame to dict
    details_dict = details.to_dict(orient="list")
    assert assert_func(details_dict), details_dict

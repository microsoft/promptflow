import contextlib
import io
import json
import os
import os.path
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from tempfile import mkdtemp

import pytest
import yaml

from promptflow._cli.pf import main
from promptflow.utils.context_utils import _change_working_dir

FLOWS_DIR = "./tests/test_configs/flows"


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


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection")
@pytest.mark.community_control_plane_cli_test
@pytest.mark.e2etest
class TestCli:
    def test_pf_version(self, capfd):
        run_pf_command("--version")
        out, err = capfd.readouterr()
        assert out == "0.0.1\n"

    def test_basic_flow_run(self) -> None:
        # fetch std out
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            run_pf_command(
                "run",
                "create",
                "--flow",
                f"{FLOWS_DIR}/web_classification",
                "--data",
                f"{FLOWS_DIR}/webClassification3.jsonl",
                "--name",
                str(uuid.uuid4()),
            )
        assert "Completed" in f.getvalue()

    def test_basic_flow_run_batch_and_eval(self) -> None:
        run_id = str(uuid.uuid4())
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            run_pf_command(
                "run",
                "create",
                "--flow",
                f"{FLOWS_DIR}/web_classification",
                "--data",
                f"{FLOWS_DIR}/webClassification3.jsonl",
                "--name",
                run_id,
            )
        assert "Completed" in f.getvalue()

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            run_pf_command(
                "run",
                "create",
                "--flow",
                f"{FLOWS_DIR}/classification_accuracy_evaluation",
                "--column-mapping",
                "groundtruth=${data.answer},prediction=${run.outputs.category}",
                "--data",
                f"{FLOWS_DIR}/webClassification3.jsonl",
                "--run",
                run_id,
            )
        assert "Completed" in f.getvalue()

    def test_submit_run_with_yaml(self):
        runs_dir = "./tests/test_configs/flows/runs/"
        run_id = str(uuid.uuid4())
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            run_pf_command(
                "run",
                "create",
                "--file",
                "./sample_bulk_run.yaml",
                "--name",
                run_id,
                cwd=f"{runs_dir}",
            )
        assert "Completed" in f.getvalue()

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            run_pf_command(
                "run",
                "create",
                "--file",
                "./sample_eval_run.yaml",
                "--run",
                run_id,
                cwd=f"{runs_dir}",
            )
        assert "Completed" in f.getvalue()

    def test_submit_batch_variant(self):
        run_id = str(uuid.uuid4())
        run_pf_command(
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--data",
            f"{FLOWS_DIR}/webClassification3.jsonl",
            "--name",
            run_id,
            "--variant",
            "${summarize_text_content.variant_0}",
        )
        detail_path = Path(FLOWS_DIR) / "web_classification" / ".runs" / run_id / "detail.json"
        with open(detail_path) as f:
            details = json.load(f)
        tuning_node = next((x for x in details["node_runs"] if x["node"] == "summarize_text_content"), None)
        # used variant_0 config, defaults using variant_1
        assert tuning_node["inputs"]["temperature"] == 0.2

    def test_pf_flow_test(self):
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--input",
            f"{FLOWS_DIR}/webClassification3.jsonl",
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / "flow.output.json"
        assert output_path.exists()

        # Test without input
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / "flow.output.json"
        assert output_path.exists()

    def test_pf_flow_with_variant(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copytree((Path(FLOWS_DIR) / "web_classification").resolve().as_posix(), temp_dir, dirs_exist_ok=True)

            with open(Path(temp_dir) / "flow.dag.yaml", "r") as f:
                flow_dict = yaml.safe_load(f)

            node_name = "summarize_text_content"
            node = next(filter(lambda item: item["name"] == node_name, flow_dict["nodes"]))
            flow_dict["nodes"].remove(node)
            flow_dict["nodes"].append({"name": node_name, "use_variants": True})
            with open(Path(temp_dir) / "flow.dag.yaml", "w") as f:
                yaml.safe_dump(flow_dict, f)

            run_pf_command(
                "flow",
                "test",
                "--flow",
                temp_dir,
                "--input",
                f"{FLOWS_DIR}/webClassification3.jsonl",
            )
            output_path = Path(temp_dir) / ".promptflow" / "flow.output.json"
            assert output_path.exists()

            run_pf_command(
                "flow",
                "test",
                "--flow",
                temp_dir,
                "--input",
                f"{FLOWS_DIR}/webClassification3.jsonl",
                "--variant",
                "${summarize_text_content.variant_1}",
            )
            output_path = Path(temp_dir) / ".promptflow" / "flow-summarize_text_content-variant_1.output.json"
            assert output_path.exists()

    def test_pf_flow_test_single_node(self):
        node_name = "fetch_text_content_from_url"
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--input",
            f"{FLOWS_DIR}/fetch_text_content_from_url_input.jsonl",
            "--node",
            node_name,
        )
        output_path = Path(FLOWS_DIR) / "web_classification" / ".promptflow" / f"flow-{node_name}.node.detail.json"
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

    def test_pf_flow_test_debug_single_node(self):
        node_name = "fetch_text_content_from_url"
        run_pf_command(
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/web_classification",
            "--input",
            f"{FLOWS_DIR}/fetch_text_content_from_url_input.jsonl",
            "--node",
            node_name,
            "--debug",
        )

    def test_flow_init(self):
        def _validate_requirement(flow_path):
            with open(flow_path) as f:
                flow_dict = yaml.safe_load(f)
            assert flow_dict.get("environment", {}).get("python_requirements_txt", None)
            assert (flow_path.parent / flow_dict["environment"]["python_requirements_txt"]).exists()

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
            _validate_requirement(Path(temp_dir) / flow_name / "flow.dag.yaml")

            jinja_name = "hello_jinja"
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
            _validate_requirement(Path(temp_dir) / flow_name / "flow.dag.yaml")
            with open(Path(temp_dir) / flow_name / ".promptflow" / "flow.tools.json", "r") as f:
                tools_dict = json.load(f)["code"]
                assert jinja_name in tools_dict
                assert len(tools_dict[jinja_name]["inputs"]) == 1
                assert tools_dict[jinja_name]["inputs"]["text"]["type"] == ["string"]
                assert tools_dict[jinja_name]["source"] == "hello.jinja2"

    @pytest.mark.skip(reason="TODO: fix this test")
    def test_flow_export(self):
        flows_dir = "./tests/test_configs/flows"
        with tempfile.TemporaryDirectory() as temp_dir:
            run_pf_command(
                "flow",
                "export",
                "--source",
                os.path.join(flows_dir, "intent-copilot"),
                "--output",
                temp_dir,
                "--format",
                "docker",
                "--encryption-key",
                "123",
            )

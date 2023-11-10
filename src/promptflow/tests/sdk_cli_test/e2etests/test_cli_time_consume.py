import contextlib
import io
import sys
import tempfile
import uuid
from pathlib import Path
import pytest
import cProfile
import pstats
from promptflow._cli._pf.entry import main
import multiprocessing

FLOWS_DIR = "./tests/test_configs/flows"
DATAS_DIR = "./tests/test_configs/datas"


def run_cli_command(cmd, time_limit=3600, is_print_stats=True, *, result_queue=None):
    sys.argv = list(cmd)
    with cProfile.Profile() as pr:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main()

        pstats_obj = pstats.Stats(pr).sort_stats(pstats.SortKey.CUMULATIVE)
        stats_profile = pstats_obj.get_stats_profile()
        if is_print_stats:
            print(pstats_obj.print_stats(50))
        assert stats_profile.total_tt < time_limit

        res_value = output.getvalue()
        if result_queue:
            result_queue.put(res_value)
        return res_value


def subprocess_run_cli_command(cmd, time_limit=3600, is_print_stats=True):
    result_queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=run_cli_command, args=(cmd,), kwargs={"time_limit": time_limit,
                                                                                   "is_print_stats": is_print_stats,
                                                                                   "result_queue": result_queue})
    process.start()
    process.join()
    assert process.exitcode == 0
    return result_queue.get_nowait()


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection")
@pytest.mark.cli_test
@pytest.mark.e2etest
class TestCliTimeConsume:
    def test_pf_run_create(self) -> None:
        res = subprocess_run_cli_command(cmd=(
            "pf",
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/print_input_flow",
            "--data",
            f"{DATAS_DIR}/print_input_flow.jsonl",
        ), time_limit=10)

        assert "Completed" in res

    def test_pf_run_update(self) -> None:
        run_name = str(uuid.uuid4())
        run_cli_command(cmd=(
            "pf",
            "run",
            "create",
            "--flow",
            f"{FLOWS_DIR}/print_input_flow",
            "--data",
            f"{DATAS_DIR}/print_input_flow.jsonl",
            "--name",
            run_name,
        ), is_print_stats=False)

        res = subprocess_run_cli_command(cmd=(
            "pf",
            "run",
            "update",
            "--name",
            run_name,
            "--set",
            "description=test pf run update"
        ), time_limit=5)

        assert "Completed" in res

    def test_pf_flow_test(self):
        subprocess_run_cli_command(cmd=(
            "pf",
            "flow",
            "test",
            "--flow",
            f"{FLOWS_DIR}/print_input_flow",
            "--inputs",
            "text=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
        ), time_limit=5)
        output_path = Path(FLOWS_DIR) / "print_input_flow" / ".promptflow" / "flow.output.json"
        assert output_path.exists()

    def test_pf_flow_build(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess_run_cli_command(cmd=(
                "pf",
                "flow",
                "build",
                "--source",
                f"{FLOWS_DIR}/print_input_flow/flow.dag.yaml",
                "--output",
                temp_dir,
                "--format",
                "docker"
            ), time_limit=10)
    #
    # def test_pfazure_run_list(self):
    #     pass
    #

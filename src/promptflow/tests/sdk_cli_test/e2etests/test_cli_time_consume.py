import cProfile
import contextlib
import io
import pstats
import sys
import tempfile
import timeit
import uuid
from pathlib import Path
from unittest import mock
import pytest
import multiprocessing
from promptflow import VERSION
from promptflow._core.operation_context import OperationContext
from promptflow._cli._user_agent import USER_AGENT as CLI_USER_AGENT  # noqa: E402

FLOWS_DIR = "./tests/test_configs/flows"
CONNECTIONS_DIR = "./tests/test_configs/connections"
DATAS_DIR = "./tests/test_configs/datas"


def run_cli_command(cmd, time_limit=3600, result_queue=None):
    from promptflow._cli._pf.entry import main
    sys.argv = list(cmd)
    output = io.StringIO()

    with cProfile.Profile() as pr:
        st = timeit.default_timer()
        with contextlib.redirect_stdout(output), mock.patch.object(
                OperationContext, "get_user_agent") as get_user_agent_fun:
            # Don't change get_user_agent_fun.return_value, dashboard needs to use.
            get_user_agent_fun.return_value = f"{CLI_USER_AGENT} promptflow/{VERSION} perf_monitor/1.0"
            main()
        ed = timeit.default_timer()

        print(f"{cmd}, \n Total time: {ed - st}s")
        assert ed - st < time_limit, f"The time limit is {time_limit}s, but it took {ed - st}s."

    pstats_obj = pstats.Stats(pr).strip_dirs().sort_stats(pstats.SortKey.CUMULATIVE)
    print("====cProfile print_stats=====")
    print(pstats_obj.print_stats(50))

    res_value = output.getvalue()
    if result_queue:
        result_queue.put(res_value)
    return res_value


def subprocess_run_cli_command(cmd, time_limit=3600):
    result_queue = multiprocessing.Queue()
    process = multiprocessing.Process(
        target=run_cli_command, args=(cmd,), kwargs={"time_limit": time_limit, "result_queue": result_queue}
    )
    process.start()
    process.join()
    assert process.exitcode == 0
    return result_queue.get_nowait()


@pytest.mark.usefixtures("use_secrets_config_file", "setup_local_connection")
@pytest.mark.perf_monitor_test
class TestCliTimeConsume:
    def test_pf_run_create(self, time_limit=8) -> None:
        res = subprocess_run_cli_command(
            cmd=(
                "pf",
                "run",
                "create",
                "--flow",
                f"{FLOWS_DIR}/print_input_flow",
                "--data",
                f"{DATAS_DIR}/print_input_flow.jsonl",
            ),
            time_limit=time_limit,
        )

        assert "Completed" in res

    def test_pf_run_update(self, time_limit=8) -> None:
        run_name = str(uuid.uuid4())
        run_cli_command(
            cmd=(
                "pf",
                "run",
                "create",
                "--flow",
                f"{FLOWS_DIR}/print_input_flow",
                "--data",
                f"{DATAS_DIR}/print_input_flow.jsonl",
                "--name",
                run_name,
            )
        )

        res = subprocess_run_cli_command(
            cmd=("pf", "run", "update", "--name", run_name, "--set", "description=test pf run update"),
            time_limit=time_limit,
        )

        assert "Completed" in res

    def test_pf_flow_test(self, time_limit=8):
        subprocess_run_cli_command(
            cmd=(
                "pf",
                "flow",
                "test",
                "--flow",
                f"{FLOWS_DIR}/print_input_flow",
                "--inputs",
                "text=https://www.youtube.com/watch?v=o5ZQyXaAv1g",
            ),
            time_limit=time_limit,
        )
        output_path = Path(FLOWS_DIR) / "print_input_flow" / ".promptflow" / "flow.output.json"
        assert output_path.exists()

    def test_pf_flow_build(self, time_limit=8):
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess_run_cli_command(
                cmd=(
                    "pf",
                    "flow",
                    "build",
                    "--source",
                    f"{FLOWS_DIR}/print_input_flow/flow.dag.yaml",
                    "--output",
                    temp_dir,
                    "--format",
                    "docker",
                ),
                time_limit=time_limit,
            )

    def test_pf_connection_create(self, time_limit=8):
        name = f"Connection_{str(uuid.uuid4())[:4]}"
        res = subprocess_run_cli_command(
            cmd=(
                "pf",
                "connection",
                "create",
                "--file",
                f"{CONNECTIONS_DIR}/azure_openai_connection.yaml",
                "--name",
                f"{name}",
            ),
            time_limit=time_limit,
        )

        assert "api_type" in res

    def test_pf_connection_list(self, time_limit=8):
        name = "connection_list"
        res = run_cli_command(
            cmd=(
                "pf",
                "connection",
                "create",
                "--file",
                f"{CONNECTIONS_DIR}/azure_openai_connection.yaml",
                "--name",
                f"{name}",
            )
        )
        assert "api_type" in res

        res = subprocess_run_cli_command(cmd=("pf", "connection", "list"), time_limit=time_limit)
        assert "api_type" in res

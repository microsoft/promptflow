# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import json
import os
import subprocess
import sys
import typing
from contextlib import contextmanager
from platform import system
from pathlib import Path

REPO_ROOT_DIR = Path(__file__).parent.parent.parent.parent
PROMPT_FLOW_TRACING_ROOT_DIR = REPO_ROOT_DIR / "src/promptflow-tracing"


def _print_red(msg: str) -> None:
    # print for prompt
    print("\033[91m" + msg + "\033[0m")


def _print_blue(msg: str) -> None:
    # print for progess
    print("\033[94m" + msg + "\033[0m")


@contextmanager
def _change_dir(dst: Path):
    cwd = os.getcwd()
    try:
        os.chdir(dst)
        yield
    finally:
        os.chdir(cwd)


def _run_cmd(cmd: typing.List[str]) -> None:
    shell = system() == "Windows"
    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=shell,
    )
    for line in p.stdout:
        line = line.decode("utf-8").rstrip()
        sys.stdout.write(line)
        sys.stdout.write("\n")
    p.communicate()


def _setup_pre_commit() -> None:
    _run_cmd(cmd=["pre-commit", "install"])


def _setup_dev_deps() -> None:
    # parse from pyproject.toml
    # we can refine this leveraging poetry export
    deps = []
    with open("pyproject.toml", mode="r", encoding="utf-8") as f:
        lines = f.readlines()
        collect_flag = False
        for line in lines:
            line = line.strip()
            if line.startswith("["):
                if "[tool.poetry.group.dev.dependencies]" in line or "[tool.poetry.group.test.dependencies]" in line:
                    collect_flag = True
                    continue
                else:
                    collect_flag = False
            if collect_flag and line:
                deps.append(line.split("=")[0].strip())
    cmd = ["pip", "install"] + deps
    _print_blue(f"Running {cmd}")
    _run_cmd(cmd)


def setup_promptflow_tracing() -> None:
    with _change_dir(PROMPT_FLOW_TRACING_ROOT_DIR):
        _print_blue("- Setting up promptflow-tracing")
        # pip install -e . from pyproject.toml
        _print_blue("- Installing promptflow-tracing from source")
        cmd = ["pip", "install", "--editable", "."]
        _print_blue(f"Running {cmd}")
        _run_cmd(cmd)
        # install dev & test dependencies
        _setup_dev_deps()
    # set up pre-commit
    _setup_pre_commit()


def create_test_resource_template() -> None:
    connections_filename = "connections.json"
    connections_template = {
        "azure_open_ai_connection": {
            "value": {
                "api_key": "aoai-api-key",
                "api_base": "aoai-api-endpoint",
                "api_version": "2023-07-01-preview",
            }
        }
    }
    with _change_dir(PROMPT_FLOW_TRACING_ROOT_DIR):
        with open(connections_filename, mode="w", encoding="utf-8") as f:
            json.dump(connections_template, f, ensure_ascii=False, indent=4)

    connections_file_path = (PROMPT_FLOW_TRACING_ROOT_DIR / connections_filename).resolve().absolute()
    prompt_msg = (
        f"Created test-required file {connections_filename!r} at {connections_file_path.as_posix()!r}, "
        "please update with your test resource(s)."
    )
    _print_red(prompt_msg)


if __name__ == "__main__":
    setup_promptflow_tracing()
    create_test_resource_template()

# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import os
import typing
from dataclasses import dataclass

from test_resources import REGISTERED_TEST_RESOURCES_FUNCTIONS
from utils import REPO_ROOT_DIR, change_cwd, print_blue, run_cmd

PROMPT_FLOW_PKGS = [
    "promptflow-tracing",
    # TODO: uncomment below lines when the packages are ready
    # "promptflow-core",
    # "promptflow-devkit",
    # "promptflow-azure",
    "promptflow[azure]",
]


def set_up_git_hook_scripts(verbose: bool) -> None:
    run_cmd(["pip", "install", "pre-commit"], verbose=False)  # ensure pre-commit is installed
    cmd = ["pre-commit", "install"]
    print_blue(f"Running {cmd} to set up the git hook scripts")
    run_cmd(cmd, verbose=verbose)


def collect_and_install_from_pyproject() -> None:
    # collect dependencies from pyproject.toml and install
    deps = []
    # cwd is already changed to the package folder in the context
    # so we can safely open pyproject.toml here
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
    print_blue(f"Running {cmd}")
    run_cmd(cmd)


def install_pkg_editable(pkg: str, verbose: bool) -> None:
    folder_name = pkg.split("[")[0]  # remove extra(s)
    pkg_working_dir = REPO_ROOT_DIR / folder_name
    print(pkg_working_dir.as_posix())
    with change_cwd(pkg_working_dir):
        print_blue(f"- Setting up {pkg}")

        # pip install -e . from pyproject.toml/setup.py
        print_blue(f"- Installing {pkg} from source")
        cmd = ["pip", "install", "--editable", "."]
        print_blue(f"Running {cmd}")
        run_cmd(cmd, verbose=verbose)

        # dev and test dependencies
        print_blue(f"- Installing dev and test dependencies for {pkg}")
        # promptflow folder has "dev_requirements.txt", directly install it
        if os.path.exists("dev_requirements.txt"):
            cmd = ["pip", "install", "-r", "dev_requirements.txt"]
            run_cmd(cmd, verbose=verbose)
        # promptflow-* will have "pyproject.toml", parse and install
        # we can refine this leveraging `poetry export` later
        elif os.path.exists("pyproject.toml"):
            collect_and_install_from_pyproject()


@dataclass
class Arguments:
    packages: typing.List[str]
    verbose: bool = False

    @staticmethod
    def parse_args() -> "Arguments":
        epilog = "Example usage: main.py --packages promptflow-tracing promptflow-core"
        parser = argparse.ArgumentParser(
            description="Welcome to promptflow dev setup!",
            epilog=epilog,
        )
        parser.add_argument(
            "--packages",
            required=False,
            nargs="+",
            type=str,
            default=PROMPT_FLOW_PKGS,
            help="packages to install in editable mode",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="turn on verbose output")
        args = parser.parse_args()
        return Arguments(
            packages=args.packages,
            verbose=args.verbose,
        )


def main(args: Arguments) -> None:
    for pkg in args.packages:
        install_pkg_editable(pkg, verbose=args.verbose)
        # invoke test resource template creation function if available
        if pkg in REGISTERED_TEST_RESOURCES_FUNCTIONS:
            REGISTERED_TEST_RESOURCES_FUNCTIONS[pkg]()
    set_up_git_hook_scripts(verbose=args.verbose)


if __name__ == "__main__":
    main(args=Arguments.parse_args())

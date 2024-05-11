# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import os
import site
import typing
import sys
from dataclasses import dataclass
from pathlib import Path

from test_resources import REGISTERED_TEST_RESOURCES_FUNCTIONS
from utils import REPO_ROOT_DIR, change_cwd, print_blue, run_cmd

PROMPT_FLOW_PKGS = [
    "promptflow-tracing",
    "promptflow-core",
    "promptflow-devkit",
    "promptflow-azure",
    "promptflow[azure]",
    "promptflow-tools",
    "promptflow-evals",
    "promptflow-recording",
]


def set_up_git_hook_scripts(verbose: bool) -> None:
    run_cmd(["pip", "install", "pre-commit"], verbose=False)  # ensure pre-commit is installed
    cmd = ["pre-commit", "install"]
    print_blue("Running `pre-commit install` to set up the git hook scripts")
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
    run_cmd(cmd)


def inject_pth_file() -> None:
    # content of the .pth file will be added to `sys.path`
    # for packages installed from pyproject.toml, this file should already be there
    # for `promptflow`, inject this, and we can avoid `conda env config vars set`
    # reference: https://docs.python.org/3/library/site.html
    site_packages_path = Path(site.getsitepackages()[0])
    with open(site_packages_path / "promptflow.pth", mode="w", encoding="utf-8") as f:
        f.write((REPO_ROOT_DIR / "src" / "promptflow").resolve().absolute().as_posix())


def install_pkg_editable(pkg: str, verbose: bool, is_vscode: bool = False) -> None:
    if "[" in pkg:
        folder_name, extras = pkg.split("[")
        extras = f"[{extras}"
    else:
        folder_name = pkg
        extras = ""
    pkg_working_dir = REPO_ROOT_DIR / "src" / folder_name
    with change_cwd(pkg_working_dir):
        print_blue(f"- Setting up {pkg}")

        # pip install -e . from pyproject.toml/setup.py
        print_blue(f"- Installing {pkg} from source")
        cmd = [sys.executable, "-m", "pip", "install", "--editable", f".{extras}"]
        run_cmd(cmd, verbose=verbose)

        # dev and test dependencies
        print_blue(f"- Installing dev and test dependencies for {pkg}")
        # promptflow folder has "dev_requirements.txt", directly install it
        if folder_name == "promptflow":
            cmd = ["pip", "install", "-r", "dev_requirements.txt"]
            run_cmd(cmd, verbose=verbose)
            inject_pth_file()
        # promptflow-tools
        # reference: https://github.com/microsoft/promptflow/blob/main/src/promptflow-tools/README.dev.md
        elif pkg == "promptflow-tools":
            cmd = ["pip", "install", "-r", "requirements.txt"]
            run_cmd(cmd, verbose=verbose)
            cmd = ["pip", "install", "pytest", "pytest-mock"]
            run_cmd(cmd, verbose=verbose)
        # promptflow-* will have "pyproject.toml", parse and install
        # we can refine this leveraging `poetry export` later
        elif os.path.exists("pyproject.toml"):
            collect_and_install_from_pyproject()

            # touch __init__.py for the package for VS Code
            # NOTE that this is a workaround to enable VS Code to recognize the namespace package
            #      we should be able to remove this after we fully deprecate promptflow in local development
            if is_vscode:
                with open(pkg_working_dir / "promptflow" / "__init__.py", mode="w", encoding="utf-8") as f:
                    f.write("__path__ = __import__('pkgutil').extend_path(__path__, __name__)\n")


@dataclass
class Arguments:
    packages: typing.List[str]
    verbose: bool = False
    vscode: bool = False

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
            help="turn on verbose output",
        )
        parser.add_argument(
            "--vscode",
            action="store_true",
            help="extra setup step for Visual Studio Code",
        )
        args = parser.parse_args()
        return Arguments(
            packages=args.packages,
            verbose=args.verbose,
            vscode=args.vscode,
        )


def main(args: Arguments) -> None:
    for pkg in args.packages:
        install_pkg_editable(pkg, verbose=args.verbose, is_vscode=args.vscode)
        # invoke test resource template creation function if available
        if pkg in REGISTERED_TEST_RESOURCES_FUNCTIONS:
            REGISTERED_TEST_RESOURCES_FUNCTIONS[pkg]()
    set_up_git_hook_scripts(verbose=args.verbose)


if __name__ == "__main__":
    main(args=Arguments.parse_args())

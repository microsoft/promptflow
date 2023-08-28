import argparse
from pathlib import Path
from platform import system

from utils import print_blue, run_command


def setup_promptflow(extra_deps: list, command_args: dict) -> None:
    print_blue("- Setting up the promptflow SDK ")
    print_blue("- Installing promptflow Python SDK from local directory")
    package_location = f"{Path('./src/promptflow/').absolute()}"
    if extra_deps:
        print_blue(f"- Installing with extra dependencies: {extra_deps}")
        extra_deps = ",".join(extra_deps)
        package_location = f"{package_location}[{extra_deps}]"
    cmds = ["pip", "install", "-e", package_location]
    print_blue(f"Running {cmds}")
    run_command(commands=cmds, **command_args)
    run_command(
        commands=["pip", "install", "-r", str(Path("./src/promptflow/dev_requirements.txt").absolute())],
        **command_args,
    )


if __name__ == "__main__":
    epilog = """
    Sample Usages:
        python scripts/building/dev_setup.py
        python scripts/building/dev_setup.py --promptflow-extra-deps azure
    """
    parser = argparse.ArgumentParser(
        description="Welcome to promptflow dev setup!",
        epilog=epilog,
    )
    parser.add_argument(
        "--promptflow-extra-deps", required=False, nargs="+", type=str, help="extra dependencies for promptflow"
    )
    parser.add_argument("-v", "--verbose", action="store_true", required=False, help="turn on verbose output")
    args = parser.parse_args()

    command_args = {"shell": system() == "Windows", "stream_stdout": args.verbose}
    setup_promptflow(extra_deps=args.promptflow_extra_deps, command_args=command_args)
import argparse
from pathlib import Path
from platform import system

from utils import print_blue, run_command


def setup_promptflow(extra_deps: list, command_args: dict) -> None:
    print_blue("- Setting up the promptflow SDK ")
    print_blue("- Installing promptflow Python SDK from local directory")
    package_location = f"{Path('./src/promptflow-sdk/').absolute()}"
    if extra_deps:
        print_blue(f"- Installing with extra dependencies: {extra_deps}")
        extra_deps = ",".join(extra_deps)
        package_location = f"{package_location}[{extra_deps}]"
    cmds = ["pip", "install", "-e", package_location]
    print_blue(f"Running {cmds}")
    run_command(commands=cmds, **command_args)
    run_command(
        commands=["pip", "install", "-r", str(Path("./src/promptflow-sdk/dev_requirements.txt").absolute())],
        **command_args,
    )


def setup_embeddingstore(command_args):
    print_blue("- Setting up the embeddingstore SDK")
    run_command(
        commands=["pip", "install", "-e", str(Path("./src/embeddingstore-sdk/").absolute())],
        **command_args,
    )
    run_command(
        commands=["pip", "install", "-r", str(Path("./src/embeddingstore-sdk/dev_requirements.txt").absolute())],
        **command_args,
    )


if __name__ == "__main__":
    epilog = """
    Sample Usages:
        python scripts/dev_setup -pv
        python scripts/dev_setup -pv --promptflow-extra-deps azure
        """
    parser = argparse.ArgumentParser(
        description="Welcome to promptflow dev setup!",
        epilog=epilog,
    )
    parser.add_argument(
        "-p", "--promptflow", action="store_true", required=False, help="the flag to setup promptflow SDK."
    )
    parser.add_argument(
        "-e", "--embeddingstore", action="store_true", required=False, help="the flag to setup embeddingstore SDK."
    )
    parser.add_argument(
        "--promptflow-extra-deps", required=False, nargs="+", type=str, help="extra dependencies for promptflow"
    )
    parser.add_argument("-v", "--verbose", action="store_true", required=False, help="turn on verbose output")
    args = parser.parse_args()

    command_args = {"shell": system() == "Windows", "stream_stdout": args.verbose}
    if args.promptflow:
        setup_promptflow(extra_deps=args.promptflow_extra_deps, command_args=command_args)
        run_command(commands=["pre-commit", "install"], **command_args)
    if args.embeddingstore:
        setup_embeddingstore(command_args)
    print_blue("Hooray, you are all set!")

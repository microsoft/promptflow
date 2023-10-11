import argparse
from pathlib import Path
from platform import system

from utils import print_blue, run_command

def setup_promptflow(extra_deps: list, command_args: dict) -> None:
    """
    Set up the promptflow SDK, including installation and optional extra dependencies.
    
    Args:
        extra_deps (list): List of extra dependencies to install.
        command_args (dict): Additional command arguments.
    """
    print_blue("- Setting up the promptflow SDK")

    # Set the package location
    package_location = f"{Path('./src/promptflow/').absolute()}"
    if extra_deps:
        extra_deps_str = ",".join(extra_deps)
        print_blue(f"- Installing with extra dependencies: {extra_deps_str}")
        package_location = f"{package_location}[{extra_deps_str}]"

    # Install the promptflow Python SDK
    cmds = ["pip", "install", "-e", package_location]
    print_blue(f"Running: {' '.join(cmds)}")
    run_command(commands=cmds, **command_args)

    # Install development requirements
    dev_requirements_path = Path("./src/promptflow/dev_requirements.txt").absolute()
    run_command(commands=["pip", "install", "-r", str(dev_requirements_path)], **command_args)

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
        "--promptflow-extra-deps", required=False, nargs="+", type=str, help="Extra dependencies for promptflow"
    )

    parser.add_argument("-v", "--verbose", action="store_true", required=False, help="Turn on verbose output")

    args = parser.parse_args()

    command_args = {"shell": system() == "Windows", "stream_stdout": args.verbose}
    setup_promptflow(extra_deps=args.promptflow_extra_deps, command_args=command_args)

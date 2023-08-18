import argparse
import os
from pathlib import Path

from utils import Color, run_command

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=Color.RED + "Test Coverage for Promptflow!" + Color.END + "\n")

    parser.add_argument("-p", required=True, nargs="+", help="The paths to calculate code coverage")
    parser.add_argument("-t", required=True, nargs="+", help="The path to the tests")
    parser.add_argument("-l", required=True, help="Location to run tests in")
    parser.add_argument("-m", required=True, help="Pytest marker to identify the tests to run", default="all")
    parser.add_argument("-n", help="Pytest number of process to run the tests", default="15")
    parser.add_argument("--model-name", help="The model file name to run the tests", type=str, default="")
    parser.add_argument("--timeout", help="Timeout for individual tests (seconds)", type=str, default="")
    parser.add_argument("--coverage-config", help="The path of code coverage config file", type=str, default="")

    args = parser.parse_args()
    print("Working directory: " + str(os.getcwd()))
    print("Args.p: " + str(args.p))
    print("Args.t: " + str(args.t))
    print("Args.l: " + str(args.l))
    print("Args.m: " + str(args.m))
    print("Args.model-name: " + str(args.model_name))
    print("Args.coverage-config: " + str(args.coverage_config))

    cov_path_list = [f"--cov={path}" for path in args.p]
    test_paths_list = [str(Path(path).absolute()) for path in args.t]
    # display a list of all Python packages installed in the current Python environment
    run_command(["pip", "list"])
    run_command(["pip", "show", "promptflow", "promptflow-sdk"])

    pytest_command = (
        # We want the logs related to each test case can be viewed from the Azure DevOps UI.
        # The logs are stored as "attachments" to the test results.
        #
        # Currently, the "attachments" feature is only supported for nunit and VisualStudioTest(trx).
        # We choose nunit for our case. See the following link for more details:
        # https://learn.microsoft.com/en-us/azure/devops/pipelines/tasks/reference/publish-test-results-v2?view=azure-pipelines&tabs=nunit3%2Cnunit3attachments%2Cyaml#attachments-support
        ["pytest", "--nunit-xml=test-results.xml"]
        + test_paths_list  # noqa: W503
        + cov_path_list  # noqa: W503
        + [  # noqa: W503
            "--cov-branch",
            "--cov-report=html",
            "--cov-report=xml",
            "-ra",
            # f"--location={args.l}",
            "-n",
            args.n,
            "--dist",
            "loadgroup",
            "-vv",
        ]
        + [
            "--log-level=info",
            "--log-format=%(asctime)s %(levelname)s %(message)s",
            "--log-date-format=[%Y-%m-%d %H:%M:%S]",
        ]
    )

    if args.timeout:
        pytest_command = pytest_command + ["--timeout", args.timeout, "--timeout_method", "thread"]

    if args.m != "all":
        pytest_command = pytest_command + ["-m", args.m]

    if args.model_name:
        pytest_command = pytest_command + ["--model-name", args.model_name]

    if args.coverage_config:
        pytest_command = pytest_command + [f"--cov-config={args.coverage_config}"]

    # pytest --nunit-xml=test-results.xml --cov=azure.ai.ml --cov-report=html --cov-report=xml -ra ./tests/*/unittests/
    run_command(pytest_command, throw_on_retcode=False)

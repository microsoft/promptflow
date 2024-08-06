# Enforce the check of pipelines.
# This script will get the diff of the current branch and main branch, calculate the pipelines that should be triggered.
# Then it will check if the triggered pipelines are successful. This script will loop for 30*loop-times seconds at most.

# How many checks are triggered:
# 1. sdk checks: sdk_cli_tests, sdk_cli_azure_test, sdk_cli_global_config_tests are triggered.
# 2. examples checks: this script calculate the path filters and decide what should be triggered.

# Trigger checks and return the status of the checks:
# 1. If examples are not correctly generated, fail.
# 2. If required pipelines are not triggered within 6 rounds of loops, fail.
#     2.1 (special_care global variable could help on some pipelines that need to bypass the check)

# Check pipelines succeed or not:
# 1. These pipelines should return status within loop-times rounds.
# 2. If there is failed pipeline in the triggered pipelines, fail.

# Import necessary libraries
import os
import fnmatch
import subprocess
import time
import argparse
import json
import sys

# Define variables
github_repository = "microsoft/promptflow"
snippet_debug = os.getenv("SNIPPET_DEBUG", 0)
merge_commit = ""
loop_times = 40  # 40 * 30 seconds = 20 minutes
github_workspace = os.path.expanduser("~/promptflow/")

# Special cases for pipelines that need to be triggered more or less than default value 1.
# If 0, the pipeline will not be ignored in check enforcer.
# Please notice that the key should be the Job Name in the pipeline.
special_care = {
    "sdk_cli_tests": 4,
    "sdk_cli_azure_test_replay": 4,
    "sdk_cli_global_config_tests": 1,
    "tracing-e2e-test": 12,
    "tracing-unit-test": 12,
    "core_test": 4,
    "azureml_serving_test": 4,
    # "samples_connections_connection": 0,
}

# Copy from original yaml pipelines
checks = {
    "sdk_cli_tests": [
        "src/promptflow-core/**",
        "src/promptflow-devkit/**",
        "src/promptflow/**",
        "src/promptflow-tracing/**",
        "scripts/building/**",
        "src/promptflow-recording/**",
    ],
    "sdk_cli_global_config_tests": [
        "src/promptflow-core/**",
        "src/promptflow-devkit/**",
        "src/promptflow-tracing/**",
        "src/promptflow-azure/**",
        "src/promptflow/**",
        "scripts/building/**",
    ],
    "sdk_cli_azure_test_replay": [
        "src/promptflow/**",
        "scripts/building/**",
        "src/promptflow-tracing/**",
        "src/promptflow-core/**",
        "src/promptflow-devkit/**",
        "src/promptflow-azure/**",
    ],
    "tracing-e2e-test": [
        "src/promptflow-tracing/**",
    ],
    "tracing-unit-test": [
        "src/promptflow-tracing/**",
    ],
    "core_test": [
        "src/promptflow-tracing/**",
        "src/promptflow-core/**",
    ],
    "azureml_serving_test": [
        "src/promptflow-tracing/**",
        "src/promptflow-core/**",
    ],
}

reverse_checks = {}
pipelines = {}
pipelines_count = {}
failed_reason = ""


# Define functions
def trigger_checks(valid_status_array):
    global failed_reason
    global github_repository
    global merge_commit
    global snippet_debug
    global pipelines
    global pipelines_count

    output = subprocess.check_output(
        f"gh api /repos/{github_repository}/commits/{merge_commit}/check-suites?per_page=100",
        shell=True,
    )
    check_suites = json.loads(output)["check_suites"]
    for suite in check_suites:
        if snippet_debug != 0:
            print(f"check-suites id {suite['id']}")
        suite_id = suite["id"]
        output = subprocess.check_output(
            f"gh api /repos/{github_repository}/check-suites/{suite_id}/check-runs?per_page=100",
            shell=True,
        )
        check_runs = json.loads(output)["check_runs"]
        for run in check_runs:
            if snippet_debug != 0:
                print(f"check runs name {run['name']}")
            for key in pipelines.keys():
                value = pipelines[key]
                if value == 0:
                    continue
                if key in run["name"]:
                    pipelines_count[key] += 1
                    valid_status_array.append(run)

    for key in pipelines.keys():
        if pipelines_count[key] < pipelines[key]:
            print(
                f"[Failure]Pipeline {key} is triggered {pipelines_count[key]} times, less than {pipelines[key]} times."
            )
            failed_reason = "Not all pipelines are triggered."
        else:
            print(
                f"Pipeline {key} is triggered {pipelines_count[key]} times, more or equal to {pipelines[key]} times."
            )


def status_checks(valid_status_array):
    global failed_reason
    global pipelines
    global pipelines_count
    # Basic fact of sdk cli checked pipelines.
    failed_reason = ""

    # Loop through each valid status array.
    for status in valid_status_array:
        # Check if the pipeline was successful.
        if status["conclusion"] and status["conclusion"].lower() == "success":
            # Add 1 to the count of successful pipelines.
            pass
        # Check if the pipeline failed.
        elif status["conclusion"] and status["conclusion"].lower() == "failure":
            failed_reason = "Required pipelines are not successful."
        # Check if the pipeline is still running.
        else:
            if failed_reason == "":
                failed_reason = "Required pipelines are not finished."
        # Print the status of the pipeline to the console.
        print(status["name"] + " is checking.")


def trigger_prepare(input_paths):
    global github_workspace
    global checks
    global reverse_checks
    global pipelines
    global pipelines_count
    global failed_reason
    global special_care

    for input_path in input_paths:
        if "samples_connections_connection" in input_path:
            continue
        # Check if the input path contains "examples" or "samples".
        if "examples" in input_path or "samples" in input_path:
            sys.path.append(os.path.expanduser(github_workspace + "/scripts/readme"))
            from readme import main as readme_main

            os.chdir(os.path.expanduser(github_workspace))

            # Get the list of pipelines from the readme file.
            pipelines_samples = readme_main(check=True)

            git_diff_files = [
                item
                for item in subprocess.check_output(
                    ["git", "diff", "--name-only", "HEAD"]
                )
                .decode("utf-8")
                .split("\n")
                if item != ""
            ]
            for _ in git_diff_files:
                failed_reason = "Run readme generation before check in"
                return
            # Merge the pipelines from the readme file with the original list of pipelines.
            for key in pipelines_samples.keys():
                value = pipelines_samples[key]
                checks[key] = value

    # Reverse checks.
    for key in checks.keys():
        value = checks[key]
        for path in value:
            if path in reverse_checks:
                reverse_checks[path].append(key)
            else:
                reverse_checks[path] = [key]

    # Render pipelines and pipelines_count using input_paths.
    for input_path in input_paths:
        # Input pattern /**: input_path should match in the middle.
        # Input pattern /*: input_path should match last but one.
        # Other input pattern: input_path should match last.

        # Skip if input path is a markdown file.
        if input_path.endswith(".md"):
            continue

        keys = [
            key for key in reverse_checks.keys() if fnmatch.fnmatch(input_path, key)
        ]
        # Loop through each key in the list of keys.
        for key_item in keys:
            # Loop through each pipeline in the list of pipelines.
            for key in reverse_checks[key_item]:
                # Check if the pipeline is in the list of pipelines.
                if key in special_care:
                    pipelines[key] = special_care[key]
                else:
                    pipelines[key] = 1
                # Set the pipeline count to 0.
                pipelines_count[key] = 0


def run_checks():
    global github_repository
    global snippet_debug
    global merge_commit
    global loop_times
    global github_workspace
    global failed_reason

    if merge_commit == "":
        merge_commit = (
            subprocess.check_output(["git", "log", "-1"]).decode("utf-8").split("\n")
        )
        if snippet_debug != 0:
            print(merge_commit)
        for line in merge_commit:
            if "Merge" in line and "into" in line:
                merge_commit = line.split(" ")[-3]
                break
    if snippet_debug != 0:
        print("MergeCommit " + merge_commit)

    not_started_counter = 5

    os.chdir(github_workspace)
    # Get diff of current branch and main branch.
    try:
        git_merge_base = (
            subprocess.check_output(["git", "merge-base", "origin/main", "HEAD"])
            .decode("utf-8")
            .rstrip()
        )
        git_diff = (
            subprocess.check_output(
                ["git", "diff", "--name-only", "--diff-filter=d", f"{git_merge_base}"],
                stderr=subprocess.STDOUT,
            )
            .decode("utf-8")
            .rstrip()
            .split("\n")
        )
        for single_diff in git_diff:
            print(single_diff)
    except subprocess.CalledProcessError as e:
        print("Exception on process, rc=", e.returncode, "output=", e.output)
        raise e

    # Prepare how many pipelines should be triggered.
    trigger_prepare(git_diff)
    if failed_reason != "":
        raise Exception(failed_reason)

    # Loop for 20 minutes at most.
    for i in range(loop_times):
        # Wait for 30 seconds.
        time.sleep(30)

        # Reset the failed reason.
        failed_reason = ""
        # Reset the valid status array.
        valid_status_array = []

        # Get all triggered pipelines.
        # If not all pipelines are triggered, continue.
        trigger_checks(valid_status_array)
        if failed_reason != "":
            if not_started_counter == 0:
                raise Exception(failed_reason + " for 6 times.")
            print(failed_reason)
            not_started_counter -= 1
            continue

        # Get pipeline conclusion priority:
        # 1. Not successful, Fail.
        # 2. Not finished, Continue.
        # 3. Successful, Break.
        status_checks(valid_status_array)

        # Check if the failed reason contains "not successful".
        if "not successful" in failed_reason.lower():
            raise Exception(failed_reason)
        # Check if the failed reason contains "not finished".
        elif "not finished" in failed_reason.lower():
            print(failed_reason)
            continue
        # Otherwise, print that all required pipelines are successful.
        else:
            print("All required pipelines are successful.")
            break

    # Check if the failed reason is not empty.
    if failed_reason != "":
        raise Exception(failed_reason)


if __name__ == "__main__":
    # Run the checks.
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-m",
        "--merge-commit",
        help="merge commit sha",
    )
    parser.add_argument(
        "-n",
        "--loop-times",
        type=int,
        help="Loop times",
    )
    parser.add_argument(
        "-t",
        "--github-workspace",
        help="base path of github workspace",
    )
    args = parser.parse_args()
    if args.merge_commit:
        merge_commit = args.merge_commit
    if args.loop_times:
        loop_times = args.loop_times
    if args.github_workspace:
        github_workspace = args.github_workspace
    run_checks()
